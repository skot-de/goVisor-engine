#!/usr/bin/env python3
"""**Dubletten-Waechter fuer Firmen** — dieselbe Firma unter mehreren `identity_id`.

Der Anlass: `H. Klostermann Baugesellschaft mbH` (Hamm) sah aus, als laege ein Viertel
ihrer Zuschlaege unter einer zweiten Entitaet, weil dieselbe Firma einmal mit und einmal
ohne Leerzeichen geschrieben wird. Die Nachmessung am 2026-09-11 hat das **widerlegt**:
beide Schreibweisen sitzen laengst unter `hr:R2404_HRB6313` (605 Zeilen mit Leerzeichen,
113 ohne), und die 507 Zuschlaege der Hauptentitaet ENTHALTEN die 107 der Nebenform
bereits. Wer beide Zahlen nebeneinanderlegt, zaehlt dieselben Zuschlaege zweimal.

⚠ **Das ist die erste Lehre und der Grund fuer dieses Skript:** eine Fragmentierung sieht
man einem Namen nicht an. `govisor.entities.normalize_company` entfernt bereits Akzente,
Klammern, Interpunktion UND Rechtsformen — zwei Schreibweisen, die sich nur darin
unterscheiden, sind schon zusammengefuehrt. Uebrig bleiben nur die Faelle, in denen die
Namen sich in einem WORT unterscheiden (`Bauges.` gegen `Baugesellschaft`), und genau die
loest keine Normalisierung auf.

## Was hier geprueft wird

Der engere Vorschlag, den dieses Skript pruefbar macht: zwei Identitaeten gehoeren
zusammen, wenn ihre Namen nach Entfernen von Leerzeichen, Interpunktion und
Gross-/Kleinschreibung IDENTISCH sind. Kein Fuzzy-Matching — das ist am 2026-07-19
gemessen verworfen worden (~24 % Fehl-Merges bei Schwelle 0,7, Fallenkatalog C5), und
dieser Waechter macht es nicht wieder auf.

Der Unterschied zur bestehenden Normalisierung ist **genau einer**: die Wortgrenzen
fallen weg. Das ist der ganze Gewinn — und die ganze Gefahr.

## Die drei Fallen, gemessen am DE-Bestand (2026-09-11)

**F1 · Grenzverschiebung.** Ohne Wortgrenze wandert ein Buchstabe ueber die
Rechtsform-Grenze: `ASE GmbH` und `ASEG mbH` werden beide zu `asegmbh`. Gemessen zwei
verschiedene Handelsregister-Eintraege (HRB232448 Bruchsal gegen HRB27950 Jena). Ebenso
`LPG mbH`/`L&P GmbH`, `BSG mbH`/`B & S GmbH`, `SIG mbH`/`S&I GmbH`, `ES Bau`/`E&S Bau`.
Erkennbar daran, dass die STAEMME — der Name OHNE Rechtsform — verschieden bleiben,
obwohl der volle Schluessel gleich ist.

⚠ Die Klasse ist GROESSER als die Zahl, die der Lauf dafuer ausweist. `beurteile` vergibt
genau EINEN Grund, den schaerfsten. Nachgemessen am 2026-09-11 (DE): **223 Paare** haben
verschiedene Staemme, 181 bekommen auch das Urteil `grenzverschiebung`, bei 42 greift
vorher `gattungsname`. Wer die Gruende zaehlt, zaehlt Urteile, nicht Eigenschaften.

**F2 · Umlaut-Loeschung.** Wer „Interpunktion entfernen" als `[^[:alnum:]]` schreibt,
LOESCHT Umlaute, statt sie zu falten: `Müller` und `Möller` werden beide zu `mller`.
Gemessen 150 Paare, die es nur in dieser Fassung gibt — darunter `Thomas Möller GmbH`
gegen `Thomas Müller GmbH` und `Uwe Möller` gegen `Uwe Müller`. Das ist Kapitel 14 der
Laender-Bibel (`Łódź` → `['d']`) an einer neuen Stelle. Dieses Skript faltet deshalb
ueber `entities.strip_accents` (ae/oe/ue/ss) und meldet den Unterschied ausdruecklich.

**F3 · Platzhaltername.** Nicht jeder Gewinnername ist ein Firmenname. Im Bestand stehen
`Bieter`, `Forstunternehmen`, `GmbH`, `Holzrückeunternehmen` und ganze Adress- und
Telefonfragmente als „Name". Zwei Identitaeten unter `Bieter` sind zwei verschiedene
Firmen, egal wie gleich der Schluessel ist.

## ⚠ Der eigentliche Fund: ein Merge ist NICHT paarweise

Jedes einzelne Paar kann belegt aussehen und die Anwendung trotzdem verheerend sein. Wer
A~B und B~C verschmilzt, verschmilzt A~C — auch wenn A und C nie verglichen wurden. Genau
daran ist die Fuzzy-Stufe am 2026-07-19 gescheitert, und die enge Regel hat denselben Sog:

    7.339 belegte Paare (solo↔solo)  →  groesster Klumpen: 1.679 Identitaeten, 25.250 Zuschlaege
    nimmt man die redaktionellen Gruppen dazu  →  3.274 Identitaeten, 96.113 Zuschlaege

Der Grund ist benennbar, und er ist kein Namensproblem. Die zwoelf Knoten mit den meisten
Kanten sind ausnahmslos Entitaeten, deren SCHLUESSEL eine Muellkennung ist —
`solo:id:keineAngabe` allein haelt 508 Kanten, `solo:id:DE` 334. Solche Entitaeten
enthalten bereits Dutzende bis Tausende fremder Firmen (`id:keineAngabe`: 1.050
verschiedene kanonisierte Namen), tragen deshalb viele Namen UND viele Postleitzahlen und
passen darum zu fast allem. Sie sind die Bruecke, ueber die fremde Firmen zusammenlaufen.

Gemessen: entfernt man diese Knoten, faellt der groesste Klumpen von **1.679 auf 79**
(1.847 der 7.339 Kanten gehen dabei weg). **Die Reihenfolge ist also vorgegeben: erst die
Kennungshygiene, dann die Namensregel.** Der Waechter rechnet diese Huelle am Ende jedes
Laufs mit und nennt die Naben beim Namen.

## Was das Skript NICHT tut

Es fuehrt nichts zusammen. Es schreibt nichts nach `data/`. Es listet Kandidaten mit
ihrem BELEG auf und sagt zu jedem, warum er verschmelzen duerfte oder eben nicht. Der
Merge selbst ist ein eigener, bewusster Schritt: die geprueften Paare gehoeren in
`data/gold/<LAND>/entity_merge_map.parquet`, die `gold.build_entities` optional liest und
die man zum Rueckgaengigmachen einfach wegnimmt.

    python3 scripts/pruefe_entity_dubletten.py                  # alle gebauten Laender
    python3 scripts/pruefe_entity_dubletten.py --land DE
    python3 scripts/pruefe_entity_dubletten.py --land DE --zeigen belegt --limit 30
    python3 scripts/pruefe_entity_dubletten.py --land DE --umlaut-probe

Rueckgabewert 1, sobald die Zahl der WIDERSPRUECHLICHEN Kandidaten die Schranke
`MAX_WIDERSPRUCH_ANTEIL` reisst — dann stimmt etwas an der Aufloesung nicht mehr, und
niemand sollte die Karte in diesem Zustand anwenden.
"""
from __future__ import annotations

import argparse
import collections
import itertools
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from govisor import laender  # noqa: E402
from govisor.entities import strip_accents  # noqa: E402
from govisor import locales  # noqa: E402

# ── SCHRANKEN (gemessen 2026-09-11 ueber DE, s. Modulkopf) ───────────────────────────
# Ein Stamm von hoechstens so vielen Zeichen ist ein Kuerzel. Dort entscheidet ein
# einzelnes Zeichen, und die Interpunktion, die die Regel wegwirft, WAR die Bedeutung:
# `S.T.E.R.N.` gegen `Stern`, `A.BB` gegen `Abb`. Gemessen 2026-09-11 (DE): 782 Paare haben
# einen solchen Stamm. 495 davon teilen eine PLZ und gelten deshalb weiter als belegt —
# die Schranke greift nur, wo der Ortszeuge FEHLT (72 Faelle).
KURZSTAMM_MAX = 6

# Ueber so vielen verschiedenen PLZ-Regionen (zwei Stellen) ist ein Name kein Firmenname
# mehr, sondern eine Gattung. `Forstunternehmen` stand auf 35315/36396/56348/72297 — vier
# Regionen, vier Firmen. Eine echte Firma mit Niederlassungen bleibt darunter; der
# hoechste ehrliche Wert im Bestand ist eine Handvoll.
GATTUNG_MIN_REGIONEN = 3

# Anteil widerspruechlicher Kandidaten, ab dem der Waechter rot wird. Gemessen 2026-09-11:
# DE 0,13 · AT 0,04 · CH 0,16 · LU 0,12. Die Schranke laesst Luft fuer Datenzuwachs, nicht
# fuer einen Regelbruch.
MAX_WIDERSPRUCH_ANTEIL = 0.30

# Ein Name, der NUR aus Rechtsform besteht, ist keiner. Exakter Vergleich auf dem Stamm,
# nicht als Teilzeichenkette — `'land '` traf einmal „Deutschland GmbH" und machte
# 211 Grossfirmen unauffindbar (Fallenkatalog C6).
_KONTAKTWORT = re.compile(r"\b(e ?mail|tel|fax|url|www|http)\b")

URTEILE = ("belegt", "widerspruch", "namensfalle", "unbelegt", "gruppenebene")


def streng(name: str) -> str:
    """Der strenge Schluessel: falten, dann alles ausser a-z0-9 weg.

    ⚠ ERST falten, DANN entfernen. Umgekehrt loescht man die Umlaute (F2).
    """
    return re.sub(r"[^a-z0-9]", "", strip_accents((name or "").lower()))


def streng_naiv(name: str) -> str:
    """Die naheliegende, falsche Fassung — nur fuer die Gegenueberstellung (`--umlaut-probe`)."""
    return re.sub(r"[^0-9a-zA-Z]", "", (name or "").lower())


def stamm(name: str, land: str) -> str:
    """Der Name OHNE Rechtsform, streng normalisiert. Traegt die Grenzverschiebung (F1)."""
    loc = locales.LOCALES.get(land) or locales.LOCALES["DE"]
    t = re.sub(r"[^a-z0-9]+", " ", strip_accents((name or "").lower()))
    return re.sub(r"[^a-z0-9]", "", loc.re_legal.sub(" ", t))


def _plz(roh: str | None) -> str | None:
    if not roh:
        return None
    p = re.sub(r"[^0-9]", "", roh)
    return p if 4 <= len(p) <= 5 else None


def _ort(roh: str | None) -> str | None:
    if not roh:
        return None
    o = re.sub(r"[^a-z]", "", strip_accents(roh.lower()))
    return o or None


_HR = re.compile(r"hr:([A-Za-z0-9_]+)")
_VAT = re.compile(r"de\s?([0-9]{9})(?![0-9])")


def _hr_schluessel(identity_id: str, entity_id: str) -> str | None:
    """Register-Schluessel, falls die Identitaet ueber das Handelsregister aufgeloest ist.

    Zwei verschiedene Registereintraege sind zwei Rechtstraeger. ⚠ Nicht immer zwei
    FIRMEN: eine `GmbH & Co. KG` fuehrt die KG im HRA und die Komplementaer-GmbH im HRB
    (gemessen an `ZwickRoell`, beide Ulm 89079). Deshalb ist ein HR-Widerspruch ein Grund
    zum Zurueckstellen, nicht zum Ausschliessen.
    """
    for s in (identity_id or "", entity_id or ""):
        m = _HR.search(s)
        if m:
            return m.group(1).lower()
    return None


def _vats(rohe: set[str]) -> set[str]:
    out: set[str] = set()
    for x in rohe:
        for m in _VAT.finditer(re.sub(r"[.\- ]", "", str(x).lower())):
            out.add(m.group(1))
    return out


def sammle(land: str, gold: pathlib.Path, silber: pathlib.Path):
    """Gewinner-Parteizeilen einlesen und je (Schluessel, Identitaet) verdichten."""
    import duckdb

    con = duckdb.connect()
    con.execute("SET threads=4")
    rows = con.execute(f"""
        SELECT p.name, ei.identity_id, pe.entity_id, p.postal_code, p.town,
               p.national_id, p.year, p.notice_id
        FROM read_parquet('{(silber / "notice_parties/**/*.parquet").as_posix()}') p
        JOIN read_parquet('{(gold / "party_entity.parquet").as_posix()}') pe
          ON pe.notice_id = p.notice_id AND pe.role = p.role AND pe.seq = p.seq
        JOIN read_parquet('{(gold / "entity_identity.parquet").as_posix()}') ei
          ON ei.entity_id = pe.entity_id
        WHERE p.role = 'winner' AND p.name IS NOT NULL
    """).fetchall()
    con.close()

    schluessel: dict[str, str] = {}
    mitglieder: dict[tuple[str, str], dict] = {}
    for name, iid, eid, plz, town, nid, jahr, nz in rows:
        s = schluessel.get(name)
        if s is None:
            s = schluessel[name] = streng(name)
        if not s:
            continue
        d = mitglieder.get((s, iid))
        if d is None:
            d = mitglieder[(s, iid)] = dict(
                identity_id=iid, entity_ids=set(), namen=collections.Counter(),
                plz=set(), ort=set(), nid=set(), jahre=set(), notices=set())
        d["entity_ids"].add(eid)
        d["namen"][name] += 1
        d["jahre"].add(jahr)
        d["notices"].add(nz)
        if (p := _plz(plz)):
            d["plz"].add(p)
        if (o := _ort(town)):
            d["ort"].add(o)
        if nid:
            d["nid"].add(str(nid)[:60])
    return mitglieder


def gruppen(mitglieder: dict, land: str) -> dict[str, list[dict]]:
    g: dict[str, list[dict]] = collections.defaultdict(list)
    for (s, _iid), d in mitglieder.items():
        d["stamm"] = stamm(d["namen"].most_common(1)[0][0], land)
        d["hr"] = _hr_schluessel(d["identity_id"], sorted(d["entity_ids"])[0])
        d["vat"] = _vats(d["nid"])
        g[s].append(d)
    return {s: v for s, v in g.items() if len(v) > 1}


def beurteile(schluessel: str, a: dict, b: dict, regionen: set[str]) -> tuple[str, str, str]:
    """Ein Paar, ein Urteil, EIN Grund — der schaerfste, der zutrifft.

    Gibt ``(urteil, grund_code, grund_text)``. Der Code ist da, damit man die Gruende
    ZAEHLEN kann: ein Sammelurteil wie „namensfalle" verdeckt sonst, dass die Haelfte
    davon gar keine Firmennamen sind, sondern Telefonnummern.

    Reihenfolge ist Beweislast, nicht Vorsicht: was den Merge verbietet, kommt vor dem,
    was ihn nur nicht belegt.
    """
    # F3 — kein Firmenname. Zuerst, weil sonst jede weitere Frage sinnlos ist.
    if _KONTAKTWORT.search(re.sub(r"[^a-z0-9]+", " ", strip_accents(
            a["namen"].most_common(1)[0][0].lower()))):
        return "namensfalle", "kontaktfragment", "kein Firmenname (Adress-/Kontaktfragment)"
    if not a["stamm"] or not b["stamm"]:
        return "namensfalle", "nur_rechtsform", "Name besteht nur aus der Rechtsform"
    if len(regionen) >= GATTUNG_MIN_REGIONEN and not (a["plz"] & b["plz"]):
        return ("namensfalle", "gattungsname",
                f"Gattungsname: {len(regionen)} PLZ-Regionen unter demselben Namen, "
                f"und diese beiden teilen keine")
    # F1 — die Wortgrenze hat einen Buchstaben ueber die Rechtsform geschoben
    if a["stamm"] != b["stamm"]:
        return ("namensfalle", "grenzverschiebung",
                f"Grenzverschiebung: Stamm {a['stamm']!r} gegen {b['stamm']!r} "
                f"(gleich wird es erst MIT Rechtsform)")
    # Harte Widersprueche
    if a["hr"] and b["hr"] and a["hr"] != b["hr"]:
        return "widerspruch", "register", f"zwei Registereintraege: {a['hr']} gegen {b['hr']}"
    if a["vat"] and b["vat"] and not (a["vat"] & b["vat"]):
        return ("widerspruch", "ustidnr",
                f"zwei USt-IdNr: DE{sorted(a['vat'])[0]} gegen DE{sorted(b['vat'])[0]}")
    if a["plz"] and b["plz"] and not (a["plz"] & b["plz"]):
        return ("widerspruch", "plz",
                f"keine gemeinsame PLZ: {sorted(a['plz'])[:2]} gegen {sorted(b['plz'])[:2]}")
    # F1b — Kuerzel ohne Ortsbeleg: ein Zeichen entscheidet, und es fehlt der Zeuge
    if len(a["stamm"]) <= KURZSTAMM_MAX and not (a["plz"] & b["plz"]):
        return "namensfalle", "kuerzel", f"Kuerzel {a['stamm']!r} ohne gemeinsame PLZ"
    # Belege
    if a["hr"] and a["hr"] == b["hr"]:
        return "belegt", "register", f"derselbe Registereintrag {a['hr']}"
    if a["vat"] & b["vat"]:
        return "belegt", "ustidnr", f"dieselbe USt-IdNr DE{sorted(a['vat'] & b['vat'])[0]}"
    if a["plz"] & b["plz"]:
        return "belegt", "plz", f"gemeinsame PLZ {sorted(a['plz'] & b['plz'])[0]}"
    if a["ort"] & b["ort"]:
        return "belegt", "ort", f"gemeinsamer Ort {sorted(a['ort'] & b['ort'])[0]}"
    if a["ort"] and b["ort"]:
        return ("widerspruch", "ort",
                f"kein gemeinsamer Ort: {sorted(a['ort'])[:2]} gegen {sorted(b['ort'])[:2]}")
    return "unbelegt", "kein_zeuge", "weder PLZ noch Ort auf einer der beiden Seiten"


def transitive_huelle(paare: list[tuple[str, str]]):
    """Was aus den Paaren wird, wenn man sie ANWENDET — plus die Knoten, die es zusammenhalten.

    Ein Waechter, der nur Paare zaehlt, misst die falsche Groesse. Verschmilzt man A~B und
    B~C, ist auch A~C verschmolzen, ohne dass die beiden je verglichen wurden. Gibt
    ``(klumpen, naben)`` zurueck: die Zusammenhangskomponenten und die Knoten mit dem
    hoechsten Grad, absteigend.
    """
    eltern: dict[str, str] = {}

    def finde(x: str) -> str:
        while eltern.get(x, x) != x:
            eltern[x] = eltern.get(eltern[x], eltern[x])
            x = eltern[x]
        return x

    grad: collections.Counter = collections.Counter()
    for x, y in paare:
        grad[x] += 1
        grad[y] += 1
        wx, wy = finde(x), finde(y)
        if wx != wy:
            eltern[wx] = wy
    komp: dict[str, set[str]] = collections.defaultdict(set)
    for k in list(eltern) + [k for k in grad]:
        komp[finde(k)].add(k)
    return [v for v in komp.values() if len(v) > 1], grad.most_common(8)


def pruefe_land(land: str, zeigen: str | None, limit: int, umlaut_probe: bool) -> tuple[dict, int]:
    gold = ROOT / "data/gold" / land
    silber = ROOT / "data/silver" / land
    if not (gold / "entity_identity.parquet").exists():
        print(f"  {land}: kein Gold — uebersprungen")
        return {}, 0

    mitglieder = sammle(land, gold, silber)
    g = gruppen(mitglieder, land)
    zaehler = collections.Counter()
    gruende = collections.Counter()
    gruppen_urteil = collections.Counter()
    beispiele = collections.defaultdict(list)
    belegte_paare: list[tuple[str, str]] = []
    zuschlaege: dict[str, set] = collections.defaultdict(set)
    for (_s, _iid), _d in mitglieder.items():
        zuschlaege[_iid] |= _d["notices"]

    for s, mems in g.items():
        regionen = {p[:2] for m in mems for p in m["plz"]}
        urteile = set()
        for a, b in itertools.combinations(mems, 2):
            u, code, grund = beurteile(s, a, b, regionen)
            gruende[(u, code)] += 1
            if u == "belegt" and (a["identity_id"].startswith("grp:")
                                  or b["identity_id"].startswith("grp:")):
                # Eine `grp:`-Identitaet ist eine redaktionelle Gruppe, kein einzelner
                # Rechtstraeger. Sie gehoert NICHT in entity_merge_map (die wirkt auf
                # entity_id), sondern in die Gruppen-Ebene — sonst verschiebt man eine
                # Produktentscheidung in die Datenpflege (Fallenkatalog C10).
                u, grund = "gruppenebene", "eine Seite ist eine redaktionelle Gruppe: " + grund
                gruende[("gruppenebene", code)] += 1
                gruende[("belegt", code)] -= 1
            zaehler[u] += 1
            urteile.add(u)
            if u == "belegt":
                belegte_paare.append((a["identity_id"], b["identity_id"]))
            if len(beispiele[u]) < 400:
                beispiele[u].append((s, a, b, grund))
        for stufe in ("widerspruch", "namensfalle", "gruppenebene", "unbelegt", "belegt"):
            if stufe in urteile:
                gruppen_urteil[stufe] += 1
                break

    paare = sum(zaehler.values())
    print(f"\n── {land} · {len(g):,} Namensgruppen mit mehr als einer Identitaet "
          f"· {paare:,} Paare")
    if not paare:
        return zaehler, 0
    print(f"  {'Urteil':<14}{'Paare':>9}{'':>4}{'Gruppen':>9}   Gruende")
    for u in URTEILE:
        if zaehler[u] or gruppen_urteil[u]:
            g_ = ", ".join(f"{c} {n:,}" for (uu, c), n in gruende.most_common()
                           if uu == u and n > 0)
            print(f"  {u:<14}{zaehler[u]:>9,}{100*zaehler[u]/paare:>7.1f} %"
                  f"{gruppen_urteil[u]:>9,}   {g_}")

    klumpen, naben = transitive_huelle(belegte_paare)
    if klumpen:
        gross = max(klumpen, key=len)
        bkm = len(set().union(*(zuschlaege[i] for i in gross))) if gross else 0
        print(f"\n  Wuerde man die {len(belegte_paare):,} belegten Paare ANWENDEN, entstuenden "
              f"{len(klumpen):,} Klumpen.")
        print(f"  Der groesste haette {len(gross):,} Identitaeten und {bkm:,} Zuschlaege — "
              f"ein Merge ist transitiv.")
        if naben:
            print("  Die Naben, ueber die Fremdes zusammenlaeuft:")
            for knoten, grad in naben[:5]:
                print(f"    {grad:>5} Kanten  {knoten[:64]}")

    if umlaut_probe:
        naiv = collections.defaultdict(set)
        for (s, iid), d in mitglieder.items():
            for name in d["namen"]:
                if (k := streng_naiv(name)):
                    naiv[k].add(iid)
        pn = {p for v in naiv.values() if len(v) > 1
              for p in itertools.combinations(sorted(v), 2)}
        pk = {p for v in g.values() if len(v) > 1
              for p in itertools.combinations(sorted(m["identity_id"] for m in v), 2)}
        print(f"\n  Umlaut-Probe: die naive Fassung (`[^[:alnum:]]`, Umlaute GELOESCHT) "
              f"erzeugt {len(pn - pk):,} Paare,")
        print(f"  die es mit korrekter Faltung nicht gibt — dort wird Müller zu Möller.")

    if zeigen:
        print(f"\n══ {land} · {zeigen} (bis {limit}) ══")
        for s, a, b, grund in beispiele[zeigen][:limit]:
            na = a["namen"].most_common(1)[0][0]
            nb = b["namen"].most_common(1)[0][0]
            print(f"  [{s[:44]}]")
            print(f"     A {na[:52]!r:56} {len(a['notices']):>5} Zuschl. {a['identity_id'][:44]}")
            print(f"     B {nb[:52]!r:56} {len(b['notices']):>5} Zuschl. {b['identity_id'][:44]}")
            print(f"     → {grund}")
    return zaehler, paare


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--land", help="nur dieses Land (Vorgabe: alle gebauten)")
    ap.add_argument("--zeigen", choices=URTEILE, help="Kandidaten dieses Urteils auflisten")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--umlaut-probe", action="store_true",
                    help="gegenueberstellen, was die naive Normalisierung zusaetzlich verschmelzen wuerde")
    a = ap.parse_args()

    codes = [a.land.upper()] if a.land else list(laender.AKTIV)
    gesamt = collections.Counter()
    paare_gesamt = 0
    for land in codes:
        z, p = pruefe_land(land, a.zeigen, a.limit, a.umlaut_probe)
        gesamt.update(z)
        paare_gesamt += p

    if not paare_gesamt:
        print("\n✓ keine Kandidaten.")
        return 0
    anteil = gesamt["widerspruch"] / paare_gesamt
    print(f"\n  Widerspruchsanteil {anteil:.2f} (Schranke {MAX_WIDERSPRUCH_ANTEIL:.2f})")
    print("  Dieses Skript hat NICHTS zusammengefuehrt und nichts geschrieben.")
    print("  Der Merge ist ein eigener Schritt: geprueft nach "
          "data/gold/<LAND>/entity_merge_map.parquet,")
    print("  die `gold.build_entities` optional liest — wegnehmen macht ihn rueckgaengig.")
    if anteil > MAX_WIDERSPRUCH_ANTEIL:
        print(f"\n⛔ Der Widerspruchsanteil reisst die Schranke. Die Regel in diesem Zustand "
              f"NICHT anwenden.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Die Sondierungspapiere gegen ihre eigenen Messdateien.

`pruefe_sondierung.py` bewacht die TRENNUNG (sondiert ist nicht aufgenommen). Dieser
Waechter hier bewacht die ZAHLEN: jede Prozentangabe in `docs/sondierung/` muss sich aus
`data/sondierung/` nachrechnen lassen.

⚠ WARUM ES DIESE DATEI GIBT. Am 2026-09-07 wurden die Papiere von Hand nachgerechnet.
436.661 Links, 31 EU-Anteile, 65 Zellen der Aufbewahrungsmatrix und 37 Domain-Prozente
stimmten exakt — und acht Stellen nicht. Die teuerste davon war lautlos:

  · `linktiefe.md` trug fuer FUENF Laender die Werte VOR dem Musterfix (AT 76,4 % statt
    31,5 %, RO 50,0 % statt 15,1 %), waehrend `00-uebersicht.md` daneben die neuen zeigte.
    Beide Papiere beschreiben dieselbe Messung, keins war als veraltet erkennbar. Der
    Neulauf hatte die Daten ersetzt und die Dokumente stehen lassen.
  · Im Fliesstext stand 64,0 %, in der Tabelle drei Zeilen darueber 65,2 %.

Beides ist Handarbeit, und Handarbeit driftet. Die Regeln unten rechnen deshalb JEDE Zahl
neu, statt Papiere gegen Papiere zu vergleichen.

⚠ WAS HIER BEWUSST NICHT DRINSTEHT: ob eine Stichprobe gross genug ist. Das ist ein
Urteil, keine Invariante — mit einer Ausnahme, Regel 7b: wenn eine spaetere Messung
DESSELBEN Landes die Groessenangabe um mehr als das Doppelte verschieben wuerde, ist das
kein Urteil mehr, sondern ein Widerspruch.

Aufruf:  python3 scripts/pruefe_sondierungszahlen.py            (0 = sauber, 1 = Befunde)
         python3 scripts/pruefe_sondierungszahlen.py --alle     (auch die stillen Regeln)
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATEN = ROOT / "data" / "sondierung"
PAPIERE = ROOT / "docs" / "sondierung"
UEBERSICHT = PAPIERE / "00-uebersicht.md"
LINKTIEFE = PAPIERE / "linktiefe.md"
HALTBARKEIT = PAPIERE / "haltbarkeit.md"

# ⚠ Diese Papiere tragen MEHRERE Laender. Ohne die Zuordnung sucht Regel 8 die Domains
# eines Sammelkapitels im falschen Land und meldet jede Zeile als Abweichung.
SAMMELPAPIERE = {
    "baltikum": ("LT", "LV", "EE"),
    "european-dynamics": ("LT", "IE", "MT", "CY"),
    "mercell": ("NO", "NL", "DK", "DE", "FI", "LU"),
}
# Papiere ohne eigenes Land — sie rechnen ueber alle.
OHNE_LAND = {"00-uebersicht", "00b-nachpruefung", "linktiefe", "haltbarkeit", "fonds-ebene"}

# Die fuenf Spalten der Aufbewahrungsmatrix in der Reihenfolge des Papiers.
MATRIX_MONATE = ("2026-06", "2026-01", "2025-06", "2024-06", "2022-06")

_ZAHL = re.compile(r"([\d.]+)")
_MB = re.compile(r"([\d.]+)\s*MB")


def _de(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _zahl(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def _tief() -> dict[str, dict]:
    """Je Land: Nennungen je Feldgruppe und Domain, aus `_tief/<land>.json`."""
    raus = {}
    for f in sorted((DATEN / "_tief").glob("*.json")):
        j = json.loads(f.read_text(encoding="utf-8"))
        raus[j["land"]] = j["gruppen"]
    return raus


def _links(gruppen: dict) -> int:
    return sum(gruppen.get("unterlagen_link", {}).values())


def _abschnitt(text: str, von: str, bis: str) -> str:
    a = text.index(von)
    b = text.index(bis, a)
    return text[a:b]


# ── die Tabellenzeilen der Papiere ────────────────────────────────────────────────────
# | **DE** | 20,4 % | 32 % | 3,3 % | ... |
_UEB_ZEILE = re.compile(
    r"^\|\s*\**([A-Z]{2})\**\s*\|\s*([\d,]+)\s*%\s*\|\s*(.*?)\s*\|\s*([\d,]+)\s*%")
# | DE | 21.920 | 748 | 3,3 % |
_LT_ZEILE = re.compile(
    r"^\|\s*\**([A-Z]{2})\**\s*\|\s*\**([\d.]+)\**\s*\|\s*\**([\d.]+)\**\s*\|\s*\**([\d,]+)\s*%")
# | **RO** | 14.080 | Vergabe | 13,2 (Median) | 6 | **154** |
_MENGE_ZEILE = re.compile(
    r"^\|\s*\**([A-Z]{2})\**\s*\|\s*([\d.]+)\s*\|\s*\**?\w+\**?\s*\|\s*~?\**?([\d,]+)"
    r"[^|]*\|\s*\**?(\d+)\**?\s*\|\s*\**?([\d.]+)")
# | **SI** | 3/3 | 3/3 | 3/3 | 3/3 | **3/3** |
_MATRIX_ZEILE = re.compile(r"^\|\s*\**([A-Z]{2})\**\s*\|" + r"([^|]*)\|" * 5)


def _offen_wert(zelle: str) -> float | None:
    """Die 'offen'-Spalte der Uebersicht.

    ⚠ SIE IST NICHT EINHEITLICH, und das ist Absicht des Papiers: `**0 %**`, `~85 %`,
    `19 / 35 %` (zwei Ebenen), `?` und `*bedingt*` stehen nebeneinander. Gelesen wird die
    ERSTE Zahl — genau so ist die Gesamtzahl in §1 gerechnet worden. Wer hier die zweite
    nimmt, bekommt fuer Polen 35 % und eine Aufteilung, die nicht mehr aufgeht.
    """
    roh = zelle.replace("*", "").replace("~", "").strip()
    if not roh or roh.startswith("?") or "bedingt" in roh:
        return None
    m = re.search(r"([\d,]+)", roh)
    return _zahl(m.group(1)) / 100 if m else None


def befunde(alle: bool = False) -> tuple[list[str], list[str]]:
    """(Befunde, Zeilen fuer --alle). Leere Befundliste = die Zahlen tragen."""
    raus: list[str] = []
    still: list[str] = []
    tief = _tief()
    gesamt = sum(_links(g) for g in tief.values())
    ueb = UEBERSICHT.read_text(encoding="utf-8")

    # 1 · Die Kopfzahl. Sie steht im ersten Absatz und traegt jeden Prozentwert des
    #     Papiers als Nenner. Driftet sie, ist jede Prozentangabe darunter falsch.
    m = re.search(r"([\d.]+)\s*\n?Ausschreibungen / ([\d.]+) Unterlagen-Links", ueb)
    if not m:
        raus.append("00-uebersicht.md: die Kopfzeile 'N Ausschreibungen / M Unterlagen-Links' "
                    "ist nicht mehr auffindbar — ohne sie faellt der Nenner weg.")
    elif int(_zahl(m.group(2))) != gesamt:
        raus.append(f"00-uebersicht.md nennt {m.group(2)} Unterlagen-Links, "
                    f"data/sondierung/_tief/ ergibt {_de(gesamt)}. "
                    f"Nach einem Neulauf muss die Kopfzeile mit.")
    else:
        still.append(f"Kopfzahl {m.group(2)} Unterlagen-Links = Summe aus _tief/")

    # 2 · Die Laendertabelle: EU-Anteil und 'ohne Verfahren' je Land.
    lt = json.loads((DATEN / "linktiefe.json").read_text(encoding="utf-8"))["laender"]
    gesehen, offen = set(), {}
    for zeile in ueb.splitlines():
        t = _UEB_ZEILE.match(zeile)
        if not t or t.group(1) not in tief:
            continue
        land, anteil, offen_zelle, ohne = t.group(1), _zahl(t.group(2)), t.group(3), _zahl(t.group(4))
        gesehen.add(land)
        offen[land] = _offen_wert(offen_zelle)
        soll = _links(tief[land]) / gesamt * 100
        if abs(anteil - soll) > 0.05:
            raus.append(f"00-uebersicht.md §2 {land}: EU-Anteil {anteil:.1f} %, "
                        f"gemessen {soll:.1f} % ({_de(_links(tief[land]))} von {_de(gesamt)}).")
        if land in lt and abs(ohne - lt[land]["ohne_verfahren_prozent"]) > 0.05:
            raus.append(f"00-uebersicht.md §2 {land}: 'ohne Verfahren' {ohne:.1f} %, "
                        f"linktiefe.json sagt {lt[land]['ohne_verfahren_prozent']:.1f} %.")
    for land in sorted(set(tief) - gesehen):
        raus.append(f"00-uebersicht.md §2 fuehrt {land} nicht, _tief/ kennt es "
                    f"({_de(_links(tief[land]))} Links). So fehlte Liechtenstein.")
    still.append(f"§2: {len(gesehen)} Laenderzeilen gegen _tief/ und linktiefe.json")

    # 3 · Die Aufteilung in §1 muss aus der Tabelle in §2 folgen. ⚠ Das ist die Regel, die
    #     den 64,0-gegen-65,2-Fall findet: zwei Zahlen desselben Papiers, drei Zeilen
    #     auseinander, und keine von beiden falsch genug, um aufzufallen.
    eins = _abschnitt(ueb, "## 1.", "## 2.")
    err = sum(_links(tief[l]) * o for l, o in offen.items() if o is not None) / gesamt * 100
    zu = sum(_links(tief[l]) * (1 - o) for l, o in offen.items() if o is not None) / gesamt * 100
    ung = sum(_links(tief[l]) for l, o in offen.items() if o is None) / gesamt * 100
    for name, soll in (("erreichbar", err), ("nicht erreichbar", zu), ("ungeklaert", ung)):
        muster = {"erreichbar": r"gemessen erreichbar[^|]*\|\s*\**([\d,]+)",
                  "nicht erreichbar": r"nicht erreichbar[^|]*\|\s*\**([\d,]+)",
                  "ungeklaert": r"ungekl[^|]*\|\s*\**([\d,]+)"}[name]
        t = re.search(muster, eins)
        if not t:
            raus.append(f"00-uebersicht.md §1: die Zeile '{name}' ist nicht mehr lesbar.")
        elif abs(_zahl(t.group(1)) - soll) > 0.1:
            raus.append(f"00-uebersicht.md §1 '{name}': {t.group(1)} %, aus der Tabelle in "
                        f"§2 gerechnet {soll:.1f} %.")
    # 3b · Und jede Prozentzahl im Fliesstext von §1 muss eine der gerechneten sein.
    erlaubt = {round(x, 1) for x in (err, zu, ung, err + zu + ung)}
    for land, o in offen.items():
        a = _links(tief[land]) / gesamt * 100
        erlaubt |= {round(a, 1)}
        if o is not None:
            erlaubt |= {round(a * o, 1), round(a * (1 - o), 1), round(o * 100, 1)}
    fliess = "\n".join(z for z in eins.splitlines() if not z.startswith("|"))
    for wert in re.findall(r"(\d{1,3},\d)\s*%", fliess):
        w = round(_zahl(wert), 1)
        if w not in erlaubt:
            raus.append(f"00-uebersicht.md §1 nennt im Text {wert} % — diese Zahl folgt aus "
                        f"keiner Zeile der Tabelle.")
            continue
        # ⚠ DIE ERLAUBTE MENGE ALLEIN REICHT NICHT. Sie enthaelt rund neunzig Werte, und
        # 64,0 stand versehentlich fuer 65,2 — deckungsgleich mit Ungarns offen-Anteil und
        # damit „erlaubt". Eine Zahl, die dicht neben einer der drei Kennzahlen liegt,
        # meint fast immer diese Kennzahl. Also muss sie sie treffen.
        for name, soll in (("erreichbar", err), ("nicht erreichbar", zu), ("ungeklaert", ung)):
            if 0.1 < abs(w - soll) <= 2.0:
                raus.append(
                    f"00-uebersicht.md §1 nennt im Text {wert} % — das liegt neben "
                    f"'{name}' ({soll:.1f} %), trifft es aber nicht. Genau so stand dort "
                    f"64,0 gegen 65,2 in der Tabelle drei Zeilen darueber.")
    still.append(f"§1: Aufteilung {err:.1f}/{zu:.1f}/{ung:.1f} aus §2 nachgerechnet")

    # 4 · linktiefe.md gegen linktiefe.json — Zeile fuer Zeile, und kein Land darf fehlen.
    #     Der Fall, der diesen Waechter ausgeloest hat.
    txt = LINKTIEFE.read_text(encoding="utf-8")
    tabelle = _abschnitt(txt, "## 2. Das Ergebnis", "## 3.")
    gesehen = set()
    for zeile in tabelle.splitlines():
        t = _LT_ZEILE.match(zeile)
        if not t or t.group(1) not in lt:
            continue
        land = t.group(1)
        gesehen.add(land)
        d, ist = lt[land], (int(_zahl(t.group(2))), int(_zahl(t.group(3))), _zahl(t.group(4)))
        if (ist[0], ist[1]) != (d["tief"], d["flach"]) or abs(ist[2] - d["ohne_verfahren_prozent"]) > 0.05:
            raus.append(f"linktiefe.md §2 {land}: {_de(ist[0])}/{_de(ist[1])} → {ist[2]:.1f} %, "
                        f"gemessen {_de(d['tief'])}/{_de(d['flach'])} → "
                        f"{d['ohne_verfahren_prozent']:.1f} %.")
    for land in sorted(set(lt) - gesehen):
        raus.append(f"linktiefe.md §2 fuehrt {land} nicht, linktiefe.json kennt es.")
    still.append(f"linktiefe.md §2: {len(gesehen)} Zeilen gegen linktiefe.json")

    # 5 · Die Aufbewahrungsmatrix. 65 Zellen, je Zelle 'da/n' — sie sind aus
    #     aufbewahrung.json ableitbar, also wird abgeleitet statt abgeschrieben.
    auf = json.loads((DATEN / "aufbewahrung.json").read_text(encoding="utf-8"))
    hb = HALTBARKEIT.read_text(encoding="utf-8")
    matrix = _abschnitt(hb, "## 14.", "## 15.")
    n_zellen = 0
    for zeile in matrix.splitlines():
        t = _MATRIX_ZEILE.match(zeile)
        if not t or t.group(1) not in auf:
            continue
        land = t.group(1)
        for spalte, monat in enumerate(MATRIX_MONATE, start=2):
            roh = t.group(spalte).replace("*", "").strip()
            zelle = re.search(r"(\d+)\s*/\s*(\d+)", roh)
            if not zelle:      # '?', '⏳', '—' sind zugelassene Nichtaussagen
                continue
            d = auf[land].get(monat)
            if not d:
                raus.append(f"haltbarkeit.md §14 {land}/{monat}: '{roh}', "
                            f"aufbewahrung.json hat dazu keine Messung.")
                continue
            n_zellen += 1
            soll = (d["zustand"].get("da", 0), d["n"])
            if (int(zelle.group(1)), int(zelle.group(2))) != soll:
                raus.append(f"haltbarkeit.md §14 {land}/{monat}: {zelle.group(0)}, "
                            f"gemessen {soll[0]}/{soll[1]}.")
    still.append(f"haltbarkeit.md §14: {n_zellen} Zellen gegen aufbewahrung.json")

    # 6 · Die Datenmengen-Tabelle: Links/Jahr aus _tief, GB/Jahr aus der Zeile selbst.
    #     ⚠ Die Formel ist Links × offen × MB / 1024 — ohne den offen-Faktor kommt fuer
    #     Belgien 80 GB statt 48 heraus, und die Summe waere um ein Drittel zu hoch.
    n_zeilen = 0
    for zeile in _abschnitt(ueb, "## 3a.", "### ⚠").splitlines():
        t = _MENGE_ZEILE.match(zeile)
        if not t or t.group(1) not in tief:
            continue
        land, links, mb, gb = t.group(1), int(_zahl(t.group(2))), _zahl(t.group(3)), _zahl(t.group(5))
        n_zeilen += 1
        if links != _links(tief[land]):
            raus.append(f"00-uebersicht.md §3a {land}: {t.group(2)} Links/Jahr, "
                        f"_tief/ sagt {_de(_links(tief[land]))}.")
        o = offen.get(land)
        if o is not None:
            soll = links * o * mb / 1024
            if abs(soll - gb) > max(1.0, gb * 0.05):
                raus.append(f"00-uebersicht.md §3a {land}: {gb:.0f} GB/Jahr, aus der Zeile "
                            f"gerechnet {soll:.0f} ({_de(links)} × {o*100:.0f} % × {mb} MB).")
        # 6b · Und der Widerspruch zwischen zwei Stichproben desselben Landes. Kein Urteil
        #      ueber die Groesse der Stichprobe — nur die Frage, ob die spaetere Messung
        #      die Zahl VERDOPPELN oder HALBIEREN wuerde. Estland stand mit 67 GB als
        #      drittgroesster Posten da, auf EINER Vergabe; 15 spaetere Proben sagen 5.
        proben = [float(x.group(1)) for m_ in auf.get(land, {}).values()
                  for h in m_["hinweise"] if (x := _MB.search(h))]
        if len(proben) >= 3 and o is not None:
            # ⚠ GLEICHE KENNZAHL GEGEN GLEICHE KENNZAHL. Rumaenien steht mit dem MEDIAN in
            # der Tabelle (13,2) und hat im Mittel 106,5 — wer das gegeneinander haelt,
            # meldet Faktor 8 und beschreibt damit nur die eigene Verwechslung. Die
            # Spannweite Median/Mittel ist im Papier ausdruecklich behandelt.
            kennzahl = statistics.median if "Median" in zeile else statistics.mean
            mit = kennzahl(proben)
            anders = links * o * mit / 1024
            if anders > gb * 2 or anders < gb / 2:
                raus.append(
                    f"00-uebersicht.md §3a {land}: die Tabelle rechnet mit {mb} MB aus "
                    f"n={t.group(4)} → {gb:.0f} GB. aufbewahrung.json haelt {len(proben)} "
                    f"Proben desselben Landes, {'Median' if 'Median' in zeile else 'Mittel'} "
                    f"{mit:.1f} MB → {anders:.0f} GB. "
                    f"Zwei Messungen, ein Land, Faktor {max(anders, gb)/max(min(anders, gb), 1):.1f}.")
    still.append(f"§3a: {n_zeilen} Mengenzeilen nachgerechnet")

    # 7 · Die Laenderkapitel. ⚠ HIER WIRD NICHT JEDE PROZENTZAHL GEPRUEFT, und das ist
    #     eine Lehre aus der ersten Fassung: die meldete 16 von 43 Zeilen als falsch, und
    #     8 davon waren gar keine Domain-Anteile. In `gr.md` steht die Prozentspalte fuer
    #     die Linktiefe, in `european-dynamics.md` fuer die Erreichbarkeit, in `fr.md` fuer
    #     einen Software-Anteil — dieselbe Zeilenform, drei andere Bedeutungen. Weitere
    #     acht Zeilen rechnen gegen den EINEN Monat (`portale_2026-06.json`) statt gegen
    #     zwoelf; Schweden 52 % ist im Juni richtig und ueber das Jahr 47,4 %.
    #     Ein Waechter, der beides nicht unterscheiden kann, erzeugt Laerm, und Laerm wird
    #     abgeschaltet. Geprueft werden deshalb nur die zwei Formen, die ihre Basis SELBST
    #     nennen.
    n_domains = 0
    for datei in sorted(PAPIERE.glob("*.md")):
        stamm = datei.stem
        if stamm in OHNE_LAND:
            continue
        laender = [l for l in SAMMELPAPIERE.get(stamm, (stamm.upper(),)) if l in tief]
        if not laender:
            continue
        zeilen = datei.read_text(encoding="utf-8").splitlines()
        in_tabelle = False
        for nr, zeile in enumerate(zeilen, 1):
            hosts = re.findall(r"`(\*?[a-z0-9][a-z0-9.\-]*\.[a-z]{2,})`", zeile)
            proz = re.findall(r"([\d,]+)\s*%", zeile)

            # 7a · Die belegte Form: „**95,8 %** (4.383 von 4.577)". Sie traegt ihre
            #      Rohzahlen mit und ist damit ohne jede Auslegung nachrechenbar.
            beleg = re.search(r"\(([\d.]+) von ([\d.]+)", zeile)
            if beleg and len(hosts) == 1 and proz:
                n, m = int(_zahl(beleg.group(1))), int(_zahl(beleg.group(2)))
                for land in laender:
                    g = tief[land].get("unterlagen_link", {})
                    ist = g.get(hosts[0].removeprefix("www."))
                    if ist is None:
                        continue
                    n_domains += 1
                    if ist != n or sum(g.values()) != m:
                        raus.append(
                            f"{datei.name}:{nr} {hosts[0]}: '{n} von {m}', gemessen "
                            f"{ist} von {sum(g.values())}.")
                    elif abs(_zahl(proz[0]) - n / m * 100) > 0.06:
                        raus.append(f"{datei.name}:{nr} {hosts[0]}: {proz[0]} %, "
                                    f"{n}/{m} sind {n / m * 100:.1f} %.")
                continue

            # 7b · Tabellen, deren Kopfzeile das Feld benennt. Nur dort ist klar, dass die
            #      Prozentspalte ein Anteil am Unterlagen-Feld ist — und nur dort werden
            #      auch Sammelzeilen geprueft. Genau eine solche Zeile war falsch:
            #      `anogov.com` + `compraspt.com` standen mit 9,3 % statt 8,8 %, weil eine
            #      dritte Domain stillschweigend mitgezaehlt war.
            if zeile.startswith("|") and re.search(r"unterlagen_link|Unterlagen-Feld", zeile):
                in_tabelle = True
                continue
            if in_tabelle and not zeile.startswith("|"):
                in_tabelle = False
            if not (in_tabelle and hosts and len(proz) == 1) or "Rest" in zeile:
                continue
            for land in laender:
                g = tief[land].get("unterlagen_link", {})
                s = sum(g.values())
                summe = 0
                for h in hosts:
                    h = h.removeprefix("www.")
                    summe += (sum(v for k, v in g.items() if k.endswith(h[1:]))
                              if h.startswith("*.") else g.get(h, 0))
                if not summe:
                    continue
                n_domains += 1
                soll, ist = _zahl(proz[0]), summe / s * 100
                if abs(soll - ist) > (1.0 if "," not in proz[0] else 0.15):
                    raus.append(f"{datei.name}:{nr} {' + '.join(hosts)}: {proz[0]} %, "
                                f"gemessen {ist:.1f} % ({_de(summe)} von {_de(s)}).")
    still.append(f"Laenderkapitel: {n_domains} Einzeldomain-Prozente gegen _tief/")
    return raus, still


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--alle", action="store_true", help="auch die Regeln zeigen, die schweigen")
    a = p.parse_args()
    if not (DATEN / "_tief").is_dir():
        print("── Sondierungszahlen ── keine Messdateien unter data/sondierung/_tief/")
        return 0
    b, still = befunde()
    print(f"── Sondierungszahlen ── {len(list((DATEN / '_tief').glob('*.json')))} Laender, "
          f"{len(list(PAPIERE.glob('*.md')))} Papiere")
    if a.alle:
        for z in still:
            print(f"  · {z}")
    if not b:
        print("  ✓ jede Zahl der Papiere folgt aus den Messdateien")
        return 0
    for z in b:
        print(f"  ⛔ {z}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

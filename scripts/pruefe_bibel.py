#!/usr/bin/env python3
"""**Bibel-Pruefung** — haelt `docs/land-onboarding.md` + `docs/laender/` ehrlich.

Eine Anleitung altert anders als Code: sie faellt nicht um, sie wird nur langsam falsch.
Am 2026-08-23 wurde die Bibel an einem Tag geschrieben und am selben Tag zweimal von der
Wirklichkeit ueberholt — sechs Zahlen drifteten binnen Stunden, und eine Aussage ueber die
Registry war schon beim Schreiben falsch.

Was dagegen hilft, sind nicht Vorsaetze, sondern Pruefungen, die LAUT scheitern. Drei
davon stehen hier; die vierte (Verweise, Vollstaendigkeit, Verankerung) liegt bereits in
`tests/test_plumbing.py`.

    Pruefung 1  Datierung       Zahl ohne Datum in der Naehe? Die altert lautlos.
    Pruefung 2  Behauptungen    Stimmt die Aussage noch? Gegen die LIVE-Daten, nicht
                                gegen das Feld, das die Antwort behauptet.
    Pruefung 3  Doppelpflege    Steht dieselbe Aussage in CLAUDE.md UND in der Bibel?
                                Dann veraltet sie an einer der beiden Stellen zuerst.

    python3 scripts/pruefe_bibel.py
    python3 scripts/pruefe_bibel.py --offen     # auch die begruendeten Ausnahmen zeigen

Rueckgabewert 1 bei einem UNERKLAERTEN Befund. Laeuft im Nachtlauf neben
`pruefe_verdrahtung.py`.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
# ⚠ Ohne diese Zeile scheitert der Lauf unter launchd und aus jedem anderen
# Arbeitsverzeichnis mit `ModuleNotFoundError: govisor` — dieselbe Falle, an der schon
# `export_web_awards.py` ausfiel (s. docs/laender/11-betrieb.md).
sys.path.insert(0, str(ROOT))
NABE = ROOT / "docs" / "land-onboarding.md"
KAPITEL = ROOT / "docs" / "laender"

# ── Pruefung 1: Datierung ───────────────────────────────────────────────────
# Eine Messung ohne Datum liest sich als Gegenwart und ist morgen falsch. Gemessen am
# 2026-08-23: von sechs undatierten Zahlen waren nach wenigen Stunden fuenf abgedriftet —
# keine Schlussfolgerung falsch, aber jede Zahl.
_ZAHL = re.compile(r"\b\d[\d.,]*\s*(%|Prozent|Zeilen|Leads|Firmen|Tabellen|Tage|Sätze|"
                   r"Codes|Einträge|MB|Kantone|Zuschläge|Bekanntmachungen|von)\b")
# Was eine Zahl vor dem Altern schuetzt. Drei Klassen, und die zweite ist der Grund,
# warum die erste Fassung 14 Befunde meldete, von denen die meisten keine waren:
#
#   Datum        „gemessen 2026-08-23"   — ausdruecklich als Momentaufnahme markiert
#   Vergangenheit „stand 12 Tage still"  — ein EREIGNIS altert nicht, es ist passiert
#   Vergleich    „31.459 → 37.896"       — traegt seinen Zeitbezug in der Form
_DATUM = re.compile(
    r"20\d\d-\d\d-\d\d|20\d\d-\d\d|gemessen|Stand |vorher|nachher|→"
    r"|\bstand\b|\bstanden\b|\bwar\b|\bwaren\b|\blief\b|\bliefen\b|\bfiel\b"
    r"|\bfielen\b|\bhaette\b|\bhätte\b|\bhaetten\b|\bhätten\b|\bwurde\b"
    r"|\bgalt\b|\bkam\b|\bkamen\b|\bbekam\b|\bzeigte\b|\berkannte\b"
    # ⚠ Auch die Mehrzahl. „damals wurden 11.448 zurueckgeholt" ist Vergangenheit,
    # `\bwurde\b` trifft sie aber nicht — die Pruefung meldete den Absatz, obwohl der
    # Text richtig war. Ein Pruefmuster, das nur den Singular kennt, erzeugt Arbeit am
    # falschen Ende: man aendert den Text, statt die Pruefung zu reparieren.
    r"|\bwurden\b|\bbrauchte\b|\bbrauchten\b|\bstieg\b|\bstiegen\b|\bblieb\b")

# Absaetze, in denen eine Zahl KEINE Messung ist. Der Grund muss sagen, warum die Zahl
# nicht altern kann — „ist halt so" ist keine Begruendung.
DATUM_AUSNAHMEN: dict[str, str] = {
    "26 Kantone": "strukturell: die Schweiz hat 26 Kantone, das aendert sich nicht",
    "drei Ebenen": "Aufbau des Vergaberechts, keine Messung",
    "vier Sonden": "Anzahl der Pruefungen, steht im Code",
    "sechs Tore": "Aufbau dieser Anleitung selbst",
    "Sperrfrist 7 Tage": "steht als SPERRE_TAGE im Code, keine Messung",
    "NUTS_AT_2024.csv": "Dateiname einer Referenz, keine Messung",
    "1.971 Codes": "Umfang des EU-NUTS-Katalogs; aendert sich nur mit einer neuen Fassung",
}


def pruefung_datierung(zeige_offen: bool = False) -> list[str]:
    fehler: list[str] = []
    offen = 0
    for datei in sorted(KAPITEL.glob("*.md")) + [NABE]:
        for absatz in datei.read_text(encoding="utf-8").split("\n\n"):
            if not _ZAHL.search(absatz) or _DATUM.search(absatz):
                continue
            if any(a in absatz for a in DATUM_AUSNAHMEN):
                offen += 1
                continue
            erste = next((z.strip() for z in absatz.splitlines() if _ZAHL.search(z)), "")
            fehler.append(f"{datei.name}: Zahl ohne Datum — {erste[:90]}")
    if offen and not zeige_offen:
        print(f"    ({offen} begruendete Ausnahmen)")
    return fehler


# ── Pruefung 2: Behauptungen gegen die Live-Daten ───────────────────────────
# Das Register enthaelt nur Aussagen, die man MESSEN kann. Jede nennt das Kapitel, das
# sie traegt — faellt die Pruefung, weiss man sofort, welche Stelle luegt.
#
# ⚠ Gegen die DATEN pruefen, nicht gegen das Feld, das die Antwort behauptet. Genau daran
# ist `has_documents` aufgeflogen: es sagt „die Quelle bewirbt Unterlagen", nicht „wir
# haben sie" — und zeigte damit fuer DE „unknown" bei 7.781 indizierten Vorgaengen.


def _behauptungen() -> list[tuple[str, str, bool, str]]:
    """(Kapitel, Aussage, stimmt_noch, Istwert)."""
    aus = []

    # Die 16 nur-DE-Tabellen sind verdrahtet (Kapitel 05/06).
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "pv", ROOT / "scripts" / "pruefe_verdrahtung.py")
    pv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pv)
    aus.append(("05/06", "OFFEN_NUR_DE ist leer (16 Tabellen verdrahtet)",
                not pv.OFFEN_NUR_DE, f"{len(pv.OFFEN_NUR_DE)} Eintraege"))

    # Regions-Ebene je Land (Kapitel 07) — steht an ZWEI Stellen und muss uebereinstimmen.
    from govisor import gold
    spec2 = importlib.util.spec_from_file_location(
        "ra", ROOT / "scripts" / "region_ableiten.py")
    ra = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(ra)
    passt = gold._REGION_STELLEN == ra.REGION_STELLEN == {"DE": 3, "AT": 4, "CH": 5}
    aus.append(("07", "Regions-Ebene DE 3 / AT 4 / CH 5, in beiden Dateien gleich",
                passt, f"{gold._REGION_STELLEN} vs {ra.REGION_STELLEN}"))

    # 26 Kantone auf 26 NUTS (Kapitel 07/14).
    from govisor import simap
    aus.append(("07", "26 Kantone auf 26 verschiedene NUTS-3",
                len(simap._KANTON_NUTS) == 26 and len(set(simap._KANTON_NUTS.values())) == 26,
                f"{len(simap._KANTON_NUTS)} Kuerzel"))

    # OCDS/DECP sind recherchiert, nicht gebaut (Kapitel 17).
    code = ""
    for ordner in ("govisor", "scripts"):
        for d in (ROOT / ordner).rglob("*.py"):
            if d.name in ("sources.py", "pruefe_bibel.py"):
                continue
            try:
                code += d.read_text(encoding="utf-8").lower()
            except (UnicodeDecodeError, OSError):
                continue
    aus.append(("17", "OCDS und DECP sind recherchiert, nicht gebaut",
                "ocds" not in code and "decp" not in code,
                "Code gefunden" if ("ocds" in code or "decp" in code) else "kein Code"))

    # Dokumentabdeckung AT/CH (Kapitel 03) — gegen die DATEN, nicht gegen has_documents.
    for land in ("AT", "CH"):
        p = ROOT / "data" / "docs" / land / "doc_text.parquet"
        aus.append(("03", f"{land} hat 0 % Dokumentabdeckung (kein Volltext-Index)",
                    not p.exists(), "doc_text.parquet vorhanden" if p.exists() else "keiner"))

    # ── Geldwache (Kapitel 11) ──────────────────────────────────────────────
    #
    # Vier Aussagen, die Kapitel 11 macht und die alle vier schon einmal NICHT stimmten.
    # Sie stehen hier, weil der Fliesstext verrotten kann, ohne dass es jemand merkt —
    # und weil jede von ihnen bei einem Rueckbau lautlos wieder falsch wuerde.
    import inspect as _inspect
    from govisor import llm as _llm

    # 1 · Die Bremse sitzt in `chat()`, nicht im Aufrufer. `succession_llm.py` postete bis
    #     zum 2026-08-24 daran vorbei und lief damit ohne jede Grenze.
    quelle_chat = _inspect.getsource(_llm.chat)
    aus.append(("11", "die Geldwache sitzt in llm.chat(), nicht im Aufrufer",
                "_geldwache()" in quelle_chat,
                "kein _geldwache()-Aufruf in chat()"))

    # 2 · Das Tagesbuch rechnet mit dem KUMULIERTEN Verbrauch, nicht mit der
    #     Kontostandsdifferenz. Letztere wird durch jede Aufladung zunichte (gemessen
    #     2026-08-24: gemeldet 0,00 $ bei tatsaechlich 36,64 $).
    quelle_tb = _inspect.getsource(_llm._tagesbuch)
    aus.append(("11", "der Tagesdeckel rechnet mit total_usage, nicht mit dem Kontostand",
                "start_verbrauch" in quelle_tb,
                "rechnet wieder mit der Kontostandsdifferenz"))

    # 3 · Die Schonung haelt dem Pruefstand Geld frei.
    aus.append(("11", "die Schonung schuetzt den Pruefstand vor der Produktion",
                _llm.SCHONUNG_USD > 0 and "pruefstand" in _llm.GESCHONT,
                f"SCHONUNG_USD={_llm.SCHONUNG_USD}, geschont={_llm.GESCHONT}"))

    # 4 · Der Bodenpreis wird per `max_price` ERZWUNGEN, nicht nur per `:floor` erbeten.
    #     ⚠ Braucht das Netz. Ist der Katalog nicht erreichbar, wird das ausgewiesen und
    #     nicht als Fehlschlag gewertet — eine Pruefung, die bei Netzproblemen rot wird,
    #     wird abgeschaltet und prueft danach gar nichts mehr.
    try:
        deckel = _llm.bodendeckel(_llm.DEFAULT_MODEL)
    except Exception:                                     # noqa: BLE001
        deckel = None
    if deckel is None:
        aus.append(("11", "der Bodenpreis wird per max_price erzwungen",
                    True, "nicht pruefbar (Katalog nicht erreichbar)"))
    else:
        prov = _llm._or_extra(_llm.DEFAULT_MODEL).get("provider", {})
        aus.append(("11", "der Bodenpreis wird per max_price erzwungen",
                    "max_price" in prov, f"provider={prov}"))

    return aus


def pruefung_behauptungen(zeige_offen: bool = False) -> list[str]:
    fehler = []
    for kapitel, aussage, stimmt, ist in _behauptungen():
        if stimmt:
            if zeige_offen:
                print(f"    ✓ [{kapitel}] {aussage}")
            continue
        fehler.append(f"Kapitel {kapitel} behauptet: {aussage!r} — ist: {ist}")
    return fehler


# ── Pruefung 3: Doppelpflege ────────────────────────────────────────────────
# CLAUDE.md fasst die Bibel zusammen, und genau das ist die Gefahr: am 2026-08-23 stand
# dort noch „16 Gold-Tabellen gibt es weiterhin nur fuer DE", Stunden nachdem sie
# verdrahtet waren. Wer eine Aussage an zwei Stellen pflegt, pflegt sie an einer nicht.
#
# Geprueft wird nicht der Wortlaut, sondern ob CLAUDE.md ZAHLEN nennt, die auch in der
# Bibel stehen — die driften zwangslaeufig auseinander.
def pruefung_doppelpflege(zeige_offen: bool = False) -> list[str]:
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    abschnitt = claude.split("docs/land-onboarding.md")[-1][:2500] if \
        "docs/land-onboarding.md" in claude else ""
    bibel = "\n".join(d.read_text(encoding="utf-8") for d in KAPITEL.glob("*.md"))
    fehler = []
    for zahl in set(re.findall(r"\b\d{1,3}(?:\.\d{3})+\b", abschnitt)):
        if zahl in bibel:
            fehler.append(f"CLAUDE.md und die Bibel nennen beide {zahl!r} — "
                          f"eine der beiden Stellen veraltet zuerst")
    return fehler


# ── Pruefung 4: Nachlauf ────────────────────────────────────────────────────
# Hat sich der Code bewegt, waehrend das Kapitel stillstand? Jedes Kapitel nennt Dateien;
# wurde eine davon NACH dem Kapitel geaendert, beschreibt es moeglicherweise etwas, das
# umgezogen ist.
#
# ⚠ Bewusst eine WARNUNG, kein Fehlschlag. `daily_leads.sh` und `sources.py` aendern sich
# staendig — wer daraus einen roten Test macht, erzeugt eine Meldung, die nach zwei Wochen
# niemand mehr liest. Der Zweck ist ein Anstoss zum Hinsehen, und Hinsehen ist billig.
#
# Ein GETIPPTES „Stand: 2026-08-24" waere die schlechtere Loesung: es verrottet in dem
# Moment, in dem jemand das Kapitel aendert und die Zeile vergisst. Das Datum kommt
# deshalb aus git.
def _git_zeit(pfad) -> int:
    import subprocess
    r = subprocess.run(["git", "log", "-1", "--format=%at", "--", str(pfad)],
                       capture_output=True, text=True, cwd=ROOT)
    return int(r.stdout.strip() or 0)


# Ab wann ein Nachlauf kein Hinweis mehr ist, sondern ein Versaeumnis.
#
# ⚠ Eine Warnung ohne Frist ist folgenlos: man kann sie beliebig lange ignorieren, und
# genau das passiert mit jeder Meldung, die nie eskaliert. Deshalb zwei Stufen — unter
# der Frist ein Anstoss zum Hinsehen, darueber ein Fehlschlag.
#
# 30 Tage, weil `daily_leads.sh` und `sources.py` sich staendig aendern: eine kuerzere
# Frist macht aus dem taeglichen Rauschen einen taeglichen Fehlschlag, und dann liest sie
# niemand mehr. Ein Kapitel, dessen Gegenstand sich einen Monat lang bewegt hat, ohne
# dass jemand hinsah, ist dagegen wirklich ein Problem.
NACHLAUF_FRIST_TAGE = 30


def pruefung_nachlauf(zeige_offen: bool = False) -> list[str]:
    import datetime as _dt
    jetzt = _dt.datetime.now().timestamp()
    zeilen, fehler = [], []
    for datei in sorted(KAPITEL.glob("*.md")):
        kap = _git_zeit(datei)
        if not kap:
            continue
        refs = set(re.findall(r"`((?:scripts|govisor|tests|web)/[\w./-]+\.\w+)`",
                              datei.read_text(encoding="utf-8")))
        juenger = sorted(r for r in refs
                         if (ROOT / r).exists() and _git_zeit(ROOT / r) > kap)
        if not juenger:
            continue
        stand = _dt.date.fromtimestamp(kap).isoformat()
        tage = int((jetzt - kap) / 86400)
        text = (f"{datei.name} (Stand {stand}, {tage} Tage) beschreibt neuere Dateien: "
                f"{', '.join(juenger[:3])}"
                + (f" (+{len(juenger)-3})" if len(juenger) > 3 else ""))
        if tage > NACHLAUF_FRIST_TAGE:
            fehler.append(text + f" — laenger als {NACHLAUF_FRIST_TAGE} Tage unbesehen")
        else:
            zeilen.append("    " + text)
    if zeilen:
        print("\n".join(zeilen))
    return fehler


def stand_uebersicht() -> None:
    """Wie alt ist jedes Kapitel? Aus git, nicht getippt."""
    import datetime as _dt
    heute = _dt.date.today()
    print(f"  {'KAPITEL':38} {'STAND':12} ALTER")
    for datei in sorted(KAPITEL.glob("*.md")) + [NABE]:
        t = _git_zeit(datei)
        if not t:
            print(f"  {datei.name:38} {'nicht in git':12}")
            continue
        d = _dt.date.fromtimestamp(t)
        print(f"  {datei.name:38} {d.isoformat():12} {(heute - d).days} Tage")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--offen", action="store_true")
    ap.add_argument("--stand", action="store_true",
                    help="nur zeigen, wie alt jedes Kapitel ist (aus git)")
    a = ap.parse_args()
    if a.stand:
        stand_uebersicht()
        return 0
    alles = []
    for name, fn in (("1: Datierung (Zahl ohne Datum)", pruefung_datierung),
                     ("2: Behauptungen gegen die Live-Daten", pruefung_behauptungen),
                     ("3: Doppelpflege mit CLAUDE.md", pruefung_doppelpflege),
                     ("4: Nachlauf (Code bewegt, Kapitel still)", pruefung_nachlauf)):
        print(f"── Pruefung {name} ──")
        f = fn(a.offen)
        alles += f
        print(f"    {len(f)} Befund(e)")
    if alles:
        print(f"\n⚠ Bibel-Pruefung: {len(alles)} Befund(e)")
        for z in alles:
            print(f"  · {z}")
        return 1
    print("\n✓ Bibel-Pruefung sauber")
    return 0


if __name__ == "__main__":
    sys.exit(main())

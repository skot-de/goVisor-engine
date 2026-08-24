#!/usr/bin/env python3
"""**Verdrahtungskarte** — wer erzeugt welche Tabelle, und wer liest sie?

Die Laender-Bibel nennt die REGELN (`_union`, Regions-Ebene je Land, Reihenfolge der
Kette) und die Dateien, in denen ein Land eingetragen wird. Was ihr fehlte, ist die
KARTE: welche Tabelle kommt aus welchem Builder, und wer haengt daran.

Genau diese Karte haette jeden Fund dieser Sitzung sofort gezeigt:

    lead_lot        Erzeuger build_lead_lot · Verbraucher export_web_leads
                    → der Erzeuger lief im DACH-Lauf nicht mit, der Verbraucher las taeglich
    buyer_stats     Erzeuger build_market_intelligence · Verbraucher export_web_leads
                    → gebaut fuer alle Laender, gelesen nur aus DE
    lead_text       Erzeuger build_lead_text · Verbraucher export_web_leads
                    → 12 Tage stille Datei

⚠ **Erzeugt, nicht getippt.** Eine von Hand gepflegte Karte verrottet mit dem ersten
Umbau — und dieses Projekt hat an einem einzigen Tag gezeigt, wie schnell das geht. Die
Karte hier liest den Quelltext und ist damit immer so aktuell wie er.

    python3 scripts/verdrahtungskarte.py                 # ganze Karte
    python3 scripts/verdrahtungskarte.py lead_lot        # eine Tabelle
    python3 scripts/verdrahtungskarte.py --waisen        # nur die auffaelligen Faelle
    python3 scripts/verdrahtungskarte.py --markdown      # fuer die Bibel

Zwei Klassen sind auffaellig und werden getrennt gemeldet:

    ERZEUGER OHNE VERBRAUCHER   gebaut, liest niemand — Rechenzeit fuer nichts
    VERBRAUCHER OHNE ERZEUGER   gelesen, baut niemand — laeuft ins Leere oder auf einen
                                Stand, den niemand auffrischt
"""
from __future__ import annotations

import argparse
import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Wo nach Verbrauchern gesucht wird. `govisor/gold.py` steht bewusst dabei: Builder lesen
# einander, und diese Kanten sind die Reihenfolge der Kette.
SUCHRAUM = ("govisor", "scripts", "web/lib", "web/app", "web/components", "app")

# Diese Endungen kommen als Quelltext in Frage.
ENDUNGEN = (".py", ".js", ".ts", ".tsx", ".sh")


# Namen der Helfer, die eine Tabelle SCHREIBEN. Die Kette benutzt mehrere; `_write` kam
# als letzter dazu und fehlte, weshalb `dim_deflator`, `entity_group` und
# `dim_company_group` faelschlich als Waisen dastanden. Wer einen neuen Schreib-Helfer
# einfuehrt, traegt ihn hier ein — sonst meldet die Karte seine Tabellen als vaterlos.
SCHREIB_HELFER = ("copy_to", "schreibe", "write_parquet", "_copy", "to_parquet", "_write")


def _erzeuger() -> dict[str, set[str]]:
    """Tabelle -> Menge der Bausteine, die sie SCHREIBEN.

    Erkannt wird das SCHREIBZIEL, nicht jede Erwaehnung. Wer jede `*.parquet`-Nennung
    mitzaehlt, haelt jeden lesenden Join fuer einen Erzeuger.

    Drei Schreibweisen kommen im Bestand vor, und jede einzelne hat beim Bauen dieser
    Karte gefehlt, bevor sie hier stand:

      1. `out = g / "x.parquet"` .. `COPY .. TO '{out}'`
      2. `copy_to(sql, "x.parquet")`        -- Ziel als ARGUMENT eines Helfers
      3. ein mehrzeiliges `COPY (..) TO '..x.parquet'`

    Fall 3 ist der Grund, warum ANWEISUNGSWEISE geprueft wird und nicht zeilenweise:
    die Zeile mit dem Dateinamen traegt dann weder "TO" noch eine Zuweisung.
    """
    aus: dict[str, set[str]] = {}
    dateien = [ROOT / "govisor" / "gold.py"]
    # ⚠ NICHT nur gold.py. Die Dokumentkette schreibt aus eigenen Modulen, mehrere
    # Tabellen entstehen in Skripten (`entity_merge_map`, `kreis_finanzen`, `hr_index`).
    # Ohne sie meldete die Karte den halben Bestand als "gelesen, baut niemand".
    dateien += sorted((ROOT / "govisor").glob("*.py"))
    dateien += sorted((ROOT / "scripts").glob("*.py"))
    for datei in dateien:
        if datei.name == "verdrahtungskarte.py":
            continue
        try:
            quelle = datei.read_text(encoding="utf-8")
            baum = ast.parse(quelle)
        except (SyntaxError, OSError, UnicodeDecodeError):
            continue
        modulname = f"{datei.parent.name}/{datei.name}"
        for knoten in ast.walk(baum):
            if isinstance(knoten, ast.FunctionDef) and knoten.name.startswith("build_"):
                _ziele(knoten, quelle, aus, knoten.name)
        # Alles ausserhalb der Builder zaehlt auf das Modul.
        _ziele(baum, quelle, aus, modulname, nur_ausserhalb_builder=True)
    return aus


def _ziele(knoten, quelle: str, aus: dict[str, set[str]], erzeuger: str,
           nur_ausserhalb_builder: bool = False) -> None:
    innerhalb = set()
    if nur_ausserhalb_builder:
        for k in ast.walk(knoten):
            if isinstance(k, ast.FunctionDef) and k.name.startswith("build_"):
                innerhalb.update(id(x) for x in ast.walk(k))
    for anweisung in ast.walk(knoten):
        if not isinstance(anweisung, ast.stmt) or anweisung is knoten:
            continue
        if id(anweisung) in innerhalb:
            continue
        code = ast.get_source_segment(quelle, anweisung) or ""
        # ⚠ In einem `COPY (SELECT … JOIN read_parquet('a') …) TO 'b'` stehen QUELLE UND
        # ZIEL in derselben Anweisung. Wer die ganze Anweisung durchsucht, macht jede
        # gelesene Tabelle zum Erzeuger — gemessen bekam `dim_cpv_label` so fuenf
        # angebliche Erzeuger, von denen vier sie nur joinen. Nur was HINTER dem letzten
        # `TO` steht, ist das Schreibziel.
        if " TO " in code:
            teile = code.split(" TO ")[-1]
        elif re.search(r"\b(out|ziel|out2|ziel2)\s*=", code) \
                or any(h in code for h in SCHREIB_HELFER):
            teile = code
        else:
            continue
        for name in re.findall(r"""["\']([\w.-]+)\.parquet["\']""", teile):
            if _ist_tabelle(name):
                aus.setdefault(name, set()).add(erzeuger)


# Was in einem f-String vor `.parquet` steht, ist nicht immer ein Tabellenname. Gemessen
# lieferte die erste Fassung 65 „Verbraucher ohne Erzeuger", und die Mehrheit waren
# Bruchstuecke: `-atverg`, `.neu`, `YYYY-MM-live`, `2026-06`. Eine Liste, die zu neun
# Zehnteln aus Rauschen besteht, liest niemand zweimal.
def _ist_tabelle(name: str) -> bool:
    """Sieht das nach einem Tabellennamen aus — oder nach einem f-String-Bruchstueck?"""
    return bool(re.fullmatch(r"[a-z][a-z0-9_]{2,}(\.[a-z0-9-]+)?", name))


def _verbraucher() -> dict[str, set[str]]:
    """Tabelle → Menge der Dateien, die sie LESEN.

    ⚠ Kommentare werden entfernt, BEVOR gesucht wird. Ein Kommentar, der erklaert, dass
    eine Tabelle abgeloest ist, machte sie sonst zum lebendigen Verbraucher — genau so
    galten `ted_dedup` und `atverg_dedup` als „wird noch verwendet", obwohl ihr einziger
    Treffer ein Nachruf war.
    """
    aus: dict[str, set[str]] = {}
    for ordner in SUCHRAUM:
        wurzel = ROOT / ordner
        if not wurzel.is_dir():
            continue
        for datei in wurzel.rglob("*"):
            if datei.suffix not in ENDUNGEN or "node_modules" in datei.parts:
                continue
            try:
                text = datei.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            zeilen = []
            for z in text.splitlines():
                gestutzt = z.lstrip()
                if gestutzt.startswith(("#", "//", "*")):
                    continue
                zeilen.append(z.split("#", 1)[0] if datei.suffix in (".py", ".sh") else z)
            code = "\n".join(zeilen)
            rel = str(datei.relative_to(ROOT))
            # ⚠ Der Treffer muss ein PFAD sein, kein Modulname: `import pyarrow.parquet`
            # passte sonst und machte „pyarrow" zu einer Tabelle mit 31 Verbrauchern.
            gefunden = set(re.findall(r"""[/'"`]([\w.-]+)\.parquet""", code))
            # ⚠ Und der wichtigste Leser nennt die Endung GAR NICHT: `_union("lead_lot")`
            # baut den Dateinamen erst zur Laufzeit. Ohne diesen Zweig waeren genau die
            # laenderfaehigen Verbraucher unsichtbar — also die, um die es hier geht.
            gefunden |= set(re.findall(r'_(?:silber_)?union\(\s*["\']([\w.-]+)["\']', code))
            for name in gefunden:
                if _ist_tabelle(name):
                    aus.setdefault(name, set()).add(rel)
    return aus


def karte() -> dict[str, dict[str, set[str]]]:
    erz, verb = _erzeuger(), _verbraucher()
    alle = set(erz) | set(verb)
    # Auf der Platte liegende Tabellen mitnehmen: eine Datei ohne jede Nennung im
    # Quelltext ist der interessanteste Fall ueberhaupt.
    for p in (ROOT / "data" / "gold").glob("*/*.parquet"):
        alle.add(p.stem)
    return {t: {"erzeuger": erz.get(t, set()),
                "verbraucher": {v for v in verb.get(t, set())
                                # Der Builder selbst ist kein Verbraucher seiner Tabelle.
                                if v != "govisor/gold.py" or not erz.get(t)}}
            for t in sorted(alle)}


def _zeile(tabelle: str, k: dict) -> str:
    e = ", ".join(sorted(k["erzeuger"])) or "—"
    v = ", ".join(sorted(k["verbraucher"])) or "—"
    return f"  {tabelle:32} {e:34} {v}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tabelle", nargs="?", help="nur diese Tabelle zeigen")
    ap.add_argument("--waisen", action="store_true",
                    help="nur Erzeuger ohne Verbraucher und umgekehrt")
    ap.add_argument("--markdown", action="store_true", help="Markdown-Tabelle ausgeben")
    a = ap.parse_args()

    k = karte()
    if a.tabelle:
        if a.tabelle not in k:
            print(f"  {a.tabelle}: unbekannt")
            return 1
        e = k[a.tabelle]
        print(f"  {a.tabelle}")
        print(f"    erzeugt von : {', '.join(sorted(e['erzeuger'])) or '— NIEMAND'}")
        print(f"    gelesen von : {', '.join(sorted(e['verbraucher'])) or '— NIEMAND'}")
        return 0

    ohne_verbraucher = [t for t, e in k.items() if e["erzeuger"] and not e["verbraucher"]]
    ohne_erzeuger = [t for t, e in k.items() if e["verbraucher"] and not e["erzeuger"]]

    if a.markdown:
        print("| Tabelle | Erzeuger | Verbraucher |")
        print("|---------|----------|-------------|")
        for t, e in k.items():
            print(f"| `{t}` | {', '.join(f'`{x}`' for x in sorted(e['erzeuger'])) or '—'} "
                  f"| {', '.join(f'`{x}`' for x in sorted(e['verbraucher'])) or '—'} |")
        return 0

    if not a.waisen:
        print(f"  {'TABELLE':32} {'ERZEUGER':34} VERBRAUCHER")
        for t, e in k.items():
            print(_zeile(t, e))
        print()

    print(f"── Erzeuger ohne Verbraucher ({len(ohne_verbraucher)}) ──")
    print("   gebaut, liest niemand — Rechenzeit fuer nichts")
    for t in ohne_verbraucher:
        print(f"    {t:32} von {', '.join(sorted(k[t]['erzeuger']))}")
    print(f"\n── Verbraucher ohne Erzeuger ({len(ohne_erzeuger)}) ──")
    print("   gelesen, baut niemand — laeuft ins Leere oder auf einen alten Stand")
    for t in ohne_erzeuger:
        leser = sorted(k[t]["verbraucher"])
        print(f"    {t:32} gelesen von {', '.join(leser[:3])}"
              + (f" (+{len(leser)-3})" if len(leser) > 3 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())

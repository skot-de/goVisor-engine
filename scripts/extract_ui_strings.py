"""Inventar der deutschen Oberflächen-Texte im Web-Frontend.

**Wozu.** Vor dem Übersetzen muss feststehen, WAS zu übersetzen ist — und zwar gemessen,
nicht geschätzt. Das Skript harvestet deutsche Literale aus den React-Dateien und aus
`lib/explorerCore.js` und schreibt sie als Katalog-Gerüst nach `web/lib/i18n/messages/`.

**Warum der deutsche Text der Schlüssel ist.** Ein Katalog mit erfundenen Schlüsseln
(`detail.luecke.buergschaft.titel`) bringt zwei Fehlerquellen mit: der Schlüssel kann
vom Text abdriften, und ein Tippfehler zeigt dem Nutzer `detail.luecke.…` statt Text.
Mit dem deutschen Satz als Schlüssel ist die deutsche Fassung immer korrekt — auch ohne
Katalog —, und eine fehlende Übersetzung fällt auf Deutsch zurück statt auf Kauderwelsch.

**Was als deutsch gilt.** Umlaut/ß ODER ein deutsches Funktionswort als ganzes Wort.
Ausgenommen sind Code-artige Zeichenketten (Klassennamen, Pfade, Datenattribute), die
sonst massenhaft mitliefen. Die Heuristik ist bewusst großzügig: ein zu viel gefundener
Text kostet eine überflüssige Katalogzeile, ein zu wenig gefundener bleibt unübersetzt.

Aufruf:  python scripts/extract_ui_strings.py [--write]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
MSG = WEB / "lib" / "i18n" / "messages"

# Deutsche Funktionswörter als ganze Wörter — fängt Sätze ohne Umlaut („Das kommt oft vor").
DEUTSCH = re.compile(
    r"[äöüÄÖÜß]|\b(der|die|das|den|dem|des|und|oder|nicht|kein|keine|keinen|ihr|euer|eure|euren|eurem|"
    r"mit|von|bei|für|aus|auf|ist|sind|war|wird|werden|wie|was|wer|wo|wenn|dann|noch|nur|schon|"
    r"mehr|alle|jede|jeder|jedes|ein|eine|einen|einem|einer|zum|zur|beim|vom|ins|im|am)\b")

# Code-artig → kein Anzeigetext: Klassennamen, Selektoren, Pfade, Ereignisnamen, Datenschlüssel.
CODE = re.compile(r"^[a-z0-9_.:/#\[\]-]+$|^[A-Z_]+$|^\w+/\w+|^https?:|^data-|^--|^\d+$")


def _ist_text(s: str) -> bool:
    s = s.strip()
    if len(s) < 3 or len(s) > 400:
        return False
    if CODE.match(s):
        return False
    if not DEUTSCH.search(s):
        return False
    # Reine Interpolation ohne eigenen Text („${a} ${b}")
    return bool(re.sub(r"\$\{[^}]*\}", "", s).strip())


def _norm(s: str) -> str:
    """Whitespace vereinheitlichen — mehrzeilige Vorlagen-Literale sind sonst nicht
    als Schlüssel benutzbar (Einrückung ändert sich beim Umformatieren)."""
    return re.sub(r"\s+", " ", s).strip()


def ernte() -> tuple[dict[str, list[str]], Counter]:
    """→ ({Text: [Fundorte]}, Zähler je Datei)."""
    treffer: dict[str, list[str]] = {}
    je_datei: Counter = Counter()
    dateien = (sorted(WEB.glob("app/**/*.tsx")) + sorted(WEB.glob("components/**/*.tsx"))
               + sorted(WEB.glob("lib/**/*.ts")) + sorted(WEB.glob("lib/**/*.tsx"))
               + [WEB / "lib" / "explorerCore.js"])
    for p in dateien:
        if not p.exists():
            continue
        s = p.read_text()
        rel = p.relative_to(WEB).as_posix()
        gefunden: set[str] = set()
        # Schon verdrahtete Stellen ausblenden, sonst misst das Skript seinen eigenen
        # Fortschritt nicht: `t("Frist")` bzw. `${tk("Frist")}` sind erledigt, der deutsche
        # Text steht aber weiterhin im Quelltext. Ohne diesen Schritt bleibt die Zahl
        # konstant, egal wie viel uebersetzt ist.
        s = re.sub(r'\bt[k]?\(\s*"(?:[^"\\\\]|\\\\.)*"\s*\)', 'ERLEDIGT', s)
        s = re.sub(r"\bt[k]?\(\s*'(?:[^'\\\\]|\\\\.)*'\s*\)", 'ERLEDIGT', s)
        # 1) String-Literale ('…', "…", `…`)
        for m in re.finditer(r'"((?:[^"\\\n]|\\.)*)"|\'((?:[^\'\\\n]|\\.)*)\'', s):
            roh = m.group(1) if m.group(1) is not None else m.group(2)
            if roh and _ist_text(roh):
                gefunden.add(_norm(roh))
        # 2) JSX-Textknoten (>Text<) — mehrzeilig, ohne Ausdrücke am Rand
        for m in re.finditer(r">([^<>{}]{3,400})<", s):
            if _ist_text(m.group(1)):
                gefunden.add(_norm(m.group(1)))
        # 3) Text in Vorlagen-Literalen zwischen HTML-Tags: >…< innerhalb von Backticks
        #    deckt explorerCore ab, wo der halbe Text so entsteht.
        for m in re.finditer(r">([^<>`]{3,400})<", s):
            t = re.sub(r"\$\{[^{}]*\}", "", m.group(1))
            if _ist_text(t):
                gefunden.add(_norm(t))
        for t in gefunden:
            treffer.setdefault(t, []).append(rel)
        je_datei[rel] = len(gefunden)
    return treffer, je_datei


def main(schreiben: bool) -> int:
    treffer, je_datei = ernte()
    print(f"{len(treffer):,} unterschiedliche deutsche Texte in "
          f"{len([k for k, v in je_datei.items() if v]):,} Dateien\n")
    for datei, n in je_datei.most_common(15):
        if n:
            print(f"  {n:>4}  {datei}")
    rest = sum(n for d, n in je_datei.items() if d not in dict(je_datei.most_common(15)))
    if rest:
        print(f"  {rest:>4}  (übrige Dateien)")

    if not schreiben:
        print("\n(--write schreibt das Katalog-Gerüst)")
        return 0

    MSG.mkdir(parents=True, exist_ok=True)
    ziel = MSG / "inventar.json"
    ziel.write_text(json.dumps(
        {t: sorted(set(orte)) for t, orte in sorted(treffer.items())},
        ensure_ascii=False, indent=1) + "\n")
    print(f"\n→ {ziel.relative_to(ROOT)} ({len(treffer):,} Einträge)")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    sys.exit(main(ap.parse_args().write))

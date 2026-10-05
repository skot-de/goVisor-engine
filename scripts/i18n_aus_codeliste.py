"""Uebersetzungen aus der amtlichen Codeliste in die Sprachdateien uebernehmen.

⚠ WARUM EIN EIGENES SKRIPT. Die Texte der Direktvergabe-Begruendung kommen als DATEN
ins Frontend (`anf.direktvergabeGrund` → `tk(...)`), nicht als Literal im Quelltext.
`test_verdrahtete_texte_sind_uebersetzt` durchsucht aber nur Literale — er bliebe
gruen, waehrend englische Nutzer deutsche Rechtsbegriffe lesen. Dieselbe Luecke wurde
gestern bei den Nichtvergabe-Gruenden gefunden.

⚠ UND WARUM NICHT VON HAND. Es sind Ausnahmetatbestaende der Vergaberichtlinien. Die
EU veroeffentlicht sie in allen Amtssprachen; sie selbst zu uebersetzen hiesse, einen
Rechtsbegriff umzudeuten. Die Quelle liefert de, en und fr — der deutsche Wortlaut ist
der Schluessel, die anderen beiden sind der Wert.

Aufruf:  python3 scripts/i18n_aus_codeliste.py [listenname ...]
"""
import json
import pathlib
import sys

REF = pathlib.Path("data/reference/eforms")
MSG = pathlib.Path("web/lib/i18n/messages")
LISTEN = ("direct-award-justification",)


def main() -> int:
    listen = sys.argv[1:] or list(LISTEN)
    neu = {"en": {}, "fr": {}}
    for liste in listen:
        p = REF / f"{liste}.json"
        if not p.exists():
            print(f"  ⚠ {p} fehlt — erst `hole_eforms_codeliste.py` laufen lassen")
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        ohne_de = 0
        for code, lab in d.items():
            de = lab.get("de")
            if not de:
                ohne_de += 1
                continue
            for s in ("en", "fr"):
                if lab.get(s):
                    neu[s][de] = lab[s]
        print(f"  {liste}: {len(d)} Codes, {ohne_de} ohne deutschen Wortlaut")

    for sprache, eintraege in neu.items():
        if not eintraege:
            continue
        f = MSG / f"flat.{sprache}.json"
        m = json.loads(f.read_text(encoding="utf-8"))
        vorher, kollision, dazu = len(m), 0, 0
        for k, v in eintraege.items():
            if k in m:
                # ⚠ Nie ueberschreiben. Eine bestehende Uebersetzung kann bewusst
                # anders lauten; sie stillschweigend zu ersetzen waere ein Eingriff in
                # fremde Arbeit.
                if m[k] != v:
                    kollision += 1
                continue
            m[k] = v
            dazu += 1
        f.write_text(json.dumps(dict(sorted(m.items())), ensure_ascii=False, indent=2)
                     + "\n", encoding="utf-8")
        print(f"  flat.{sprache}.json: {vorher} → {len(m)}  "
              f"(+{dazu}, {kollision} bestehende belassen)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Migration gegen die goVisor-Supabase einspielen.

    python3 scripts/migrate.py supabase/0013_netz_partner.sql [weitere.sql ...]

WARUM ES DIESES SKRIPT GIBT. Die DDL lief bis zum 2026-08-22 von Hand im Dashboard, weil in
einer Notiz stand, es ginge nicht anders. Das stimmte für die GETEILTE Instanz, nicht für
goVisors eigene: das Passwort liegt in `.secrets/supabase_db.txt`, der direkte Host antwortet
über IPv6. Ein benanntes Skript statt eines Einzeilers hat zwei Vorteile: die Berechtigung in
`.claude/settings.local.json` lässt sich eng darauf zuschneiden, und die Vorsichtsmassnahmen
unten stehen im Werkzeug statt in jemandes Gedächtnis.

⚠ LÖSCHENDE ANWEISUNGEN WERDEN ABGELEHNT. `drop table`, `drop column`, `truncate` und
`delete from` brauchen `--auch-loeschen`. Eine Migration, die etwas wegnimmt, will bewusst
ausgelöst werden — additive DDL kann man notfalls zurücknehmen, gelöschte Zeilen nicht.
"""
import pathlib
import re
import sys

import psycopg2

WURZEL = pathlib.Path(__file__).resolve().parent.parent
HOST = "db.tegznbkbvbbbgzhsvoza.supabase.co"
# Anweisungen, die etwas wegnehmen. Kommentare werden vor der Prüfung entfernt, sonst löst
# ein erklärender Satz („..., dann das drop table streichen") einen Fehlalarm aus.
LOESCHT = re.compile(r"\b(drop\s+(table|column|schema|database)|truncate|delete\s+from)\b", re.I)


def ohne_kommentare(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    return "\n".join(z.split("--")[0] for z in sql.splitlines())


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    auch_loeschen = "--auch-loeschen" in sys.argv
    if not args:
        print(__doc__)
        return 2

    dateien = []
    for a in args:
        p = (WURZEL / a).resolve()
        if p.parent != (WURZEL / "supabase").resolve() or p.suffix != ".sql":
            print(f"✖ nur .sql aus supabase/: {a}")
            return 2
        if not p.exists():
            print(f"✖ nicht gefunden: {a}")
            return 2
        if LOESCHT.search(ohne_kommentare(p.read_text(encoding="utf-8"))) and not auch_loeschen:
            print(f"✖ {p.name} nimmt etwas weg (drop/truncate/delete).\n"
                  f"  Bewusst auslösen: --auch-loeschen. Vorher pruefen, was verloren geht.")
            return 3
        dateien.append(p)

    pw = (WURZEL / ".secrets" / "supabase_db.txt").read_text().strip()
    con = psycopg2.connect(host=HOST, port=5432, dbname="postgres", user="postgres",
                           password=pw, sslmode="require", connect_timeout=15)
    con.autocommit = False
    fehler = 0
    try:
        for p in dateien:
            cur = con.cursor()
            try:
                cur.execute(p.read_text(encoding="utf-8"))
                con.commit()
                print(f"✓ {p.name}")
                for hinweis in (con.notices or []):
                    print("   " + hinweis.strip())
                del con.notices[:]
            except Exception as e:                      # noqa: BLE001 — Meldung ist das Ergebnis
                con.rollback()
                print(f"✖ {p.name}: {e}")
                fehler = 1
                break
    finally:
        con.close()
    return fehler


if __name__ == "__main__":
    sys.exit(main())

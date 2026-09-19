"""Der Lead-Status ueberlebt das Neuladen (`supabase/0023`, `web/lib/supabase/leadStatus.ts`).

⚠ GEFUNDEN AM 2026-09-19, beim Umbau der Status-Spalte. `setWf` setzte `l.userStatus` am
Objekt im Speicher, `logEvent` schrieb in ein Feld, das niemand sichert — kein einziger
Schreibweg nach Supabase oder localStorage im ganzen `web/`-Baum. Wer eine Sitzung lang
dreissig Vorgaenge einsortiert hatte, fand nach dem Neuladen dreissig leere Zellen.

⚠ AUFGEFALLEN IST ES AM NACHBARN, nicht am Fehler. In derselben Zeile steht der Stern, und
der persistiert seit 0017 korrekt. Zwei Klicks nebeneinander, einer ueberlebt das Neuladen
und einer nicht. Solche Asymmetrien sieht man nur, wenn man beide zufaellig vergleicht.

⚠ DIE EIGENTLICHE GEFAHR WAR DAS KOPIEREN. `watchlist.ts` und `ausgeblendet.ts` fahren
`upsert(..., { ignoreDuplicates: true })`, und das ist dort richtig: die EXISTENZ der Zeile
ist die Aussage. Hier ist es der WERT. Dasselbe Flag haette bewirkt, dass das erste Setzen
ankommt und jede Aenderung danach lautlos verpufft — ein Fehler, der beim Ausprobieren
funktioniert und erst beim zweiten Klick auftritt. Deshalb faehrt die Sonde den echten Code
statt seinen Quelltext zu lesen.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SONDE = WURZEL / "web" / "scripts" / "pruefe-leadstatus.mjs"
MODUL = WURZEL / "web" / "lib" / "supabase" / "leadStatus.ts"
MIGRATION = WURZEL / "supabase" / "0023_lead_status.sql"
SHELL = WURZEL / "web" / "components" / "explorer" / "ExplorerShell.tsx"


def _ohne_sql_kommentar(s: str) -> str:
    """⚠ `--`-Zeilen raus. Der Kopf von 0023 BEGRUENDET die Eindeutigkeit und nennt sie
    dabei woertlich — ein Wächter, der den ganzen Text liest, bleibt gruen, nachdem die
    Zeile aus der Tabelle geflogen ist (F13, an diesem Tag zum wiederholten Mal)."""
    return "\n".join(z.split("--")[0] for z in s.splitlines())


def _ohne_kommentar(s: str) -> str:
    """`//` und `/* */` raus — sonst prueft der Test die eigene Begruendung (F13)."""
    raus, i, n = [], 0, len(s)
    while i < n:
        if s[i] == "/" and i + 1 < n and s[i + 1] == "/":
            while i < n and s[i] != "\n":
                raus.append(" ")
                i += 1
            continue
        if s[i] == "/" and i + 1 < n and s[i + 1] == "*":
            while i < n and not (s[i] == "*" and i + 1 < n and s[i + 1] == "/"):
                raus.append("\n" if s[i] == "\n" else " ")
                i += 1
            raus.append("  ")
            i += 2
            continue
        raus.append(s[i])
        i += 1
    return "".join(raus)


def test_der_status_geht_wirklich_in_die_datenbank():
    """Faehrt `leadStatus.ts` uebersetzt und mit einem Attrappen-Client."""
    if not shutil.which("node"):
        return
    r = subprocess.run(["node", str(SONDE)], capture_output=True, text=True, cwd=WURZEL)
    assert r.returncode == 0, r.stdout[-1400:] + r.stderr[-500:]
    assert "geht wirklich in die Datenbank" in r.stdout


def test_die_sonde_wird_rot_wenn_das_ueberschreiben_faellt():
    """Gegenprobe: ein Waechter, der nie rot werden kann, ist keiner.

    Die Mutation ist genau der Fehler, der hier droht — das Flag der Nachbarmodule.
    """
    if not shutil.which("node"):
        return
    quelle = MODUL.read_text(encoding="utf-8")
    assert '{ onConflict: "user_id,lead_id" }' in quelle
    kaputt = quelle.replace('{ onConflict: "user_id,lead_id" }',
                            '{ onConflict: "user_id,lead_id", ignoreDuplicates: true }', 1)
    try:
        MODUL.write_text(kaputt, encoding="utf-8")
        r = subprocess.run(["node", str(SONDE)], capture_output=True, text=True, cwd=WURZEL)
        assert r.returncode != 0, (
            "die Sonde bleibt gruen, obwohl jede Statusaenderung nach der ersten verpufft")
        assert "ignoreDuplicates" in r.stdout
    finally:
        MODUL.write_text(quelle, encoding="utf-8")


def test_die_migration_traegt_die_drei_riegel():
    """Eindeutigkeit, RLS und die Werteliste.

    ⚠ Ohne `unique (user_id, lead_id)` hat `onConflict` nichts, worauf es zielen kann —
    der Upsert legt dann bei jedem Klick eine neue Zeile an, und `loadLeadStatus` bekommt
    je Vorgang mehrere Antworten in unbestimmter Reihenfolge.
    """
    sql = _ohne_sql_kommentar(MIGRATION.read_text(encoding="utf-8"))
    assert "create table if not exists public.user_lead_status" in sql
    assert re.search(r"unique\s*\(\s*user_id\s*,\s*lead_id\s*\)", sql), (
        "ohne Eindeutigkeit greift der Upsert nicht und jeder Klick legt eine Zeile an")
    assert "enable row level security" in sql and "auth.uid() = user_id" in sql, (
        "ohne RLS liest jeder Angemeldete die Einordnungen aller anderen")
    for k in ("interessant", "pruefung", "fragen", "verworfen"):
        assert k in sql, f"der Status {k!r} fehlt in der Werteliste"
    assert "titel" in sql and "buyer_name" in sql, (
        "ohne Titel und Kaeufer ist die Zeile nicht mehr deutbar, sobald der Vorgang nach "
        "der Frist aus dem Frontend-Export faellt (gleiche Begruendung wie 0017 und 0021)")


def test_die_vier_status_stimmen_mit_der_oberflaeche_ueberein():
    """⚠ Drei Listen derselben vier Werte: `WF` in explorerCore, `WF_STATUS` im Modul, die
    Werteliste in der Migration. Waechst eine, muessen alle mitwachsen — sonst lehnt die
    Datenbank den neuen Status ab, und der Nutzer sieht nur, dass nichts gespeichert wird.
    """
    kern = _ohne_kommentar((WURZEL / "web" / "lib" / "explorerCore.js").read_text(encoding="utf-8"))
    i = kern.index("const WF = {")
    ui = set(re.findall(r"^\s*(\w+)\s*:\s*\{label", kern[i:kern.index("};", i)], re.M))
    modul = set(re.findall(r'"(\w+)"', re.search(
        r"WF_STATUS = \[([^\]]*)\]", MODUL.read_text(encoding="utf-8")).group(1)))
    sql = _ohne_sql_kommentar(MIGRATION.read_text(encoding="utf-8"))
    db = set(re.findall(r"'(\w+)'", re.search(r"status in \(([^)]*)\)", sql).group(1)))
    assert ui == modul == db, (
        f"die vier Status laufen auseinander.\n  Oberflaeche: {sorted(ui)}\n"
        f"  Modul:       {sorted(modul)}\n  Datenbank:   {sorted(db)}")


def test_der_status_ist_verdrahtet():
    """⚠ Die haeufigste Fehlerklasse dieses Projekts ist „gebaut, nicht verdrahtet": ein
    korrekter Baustein, den niemand aufruft. Bei `build_lead_text` waren es 12 stille Tage.

    Hier braucht es DREI Stellen, und das Vergessen jeder einzelnen sieht anders aus:
      · `setWfFuer` fehlt → aus der Liste gesetzte Status gehen verloren, aus dem Detail
        gesetzte nicht. Der Nutzer haelt die Liste fuer kaputt.
      · `setWf` fehlt → genau umgekehrt.
      · das Laden fehlt → alles wird gespeichert und nie wieder angezeigt. Das ist der
        schlimmste Fall, weil er von aussen wie „speichert nicht" aussieht.
    """
    code = _ohne_kommentar(SHELL.read_text(encoding="utf-8"))
    assert 'from "@/lib/supabase/leadStatus"' in code, "das Modul wird gar nicht eingebunden"
    assert code.count("syncLeadStatus(") == 2, (
        f"{code.count('syncLeadStatus(')} statt 2 Schreiber. Den Status setzen beide Wege: "
        f"setWfFuer aus der Liste und setWf aus dem Detail.")
    for fn in ("function setWfFuer", "function setWf"):
        i = code.index(fn)
        assert "syncLeadStatus(" in code[i:i + 700], f"{fn} speichert nicht"
    assert "loadLeadStatus()" in code, "das Gespeicherte wird nie wieder gelesen"
    i = code.index("loadLeadStatus()")
    fenster = code[i:i + 500]
    assert "userStatus" in fenster, (
        "das Geladene wird nicht an die Leads geschrieben — die Tabelle rendert aus dem "
        "Lead-Objekt, ein State daneben erreicht sie nicht")
    assert "bump()" in fenster, (
        "nach dem Nachladen wird nicht neu gezeichnet. Die Daten kommen aus dem Netz, also "
        "nach dem ersten Zeichnen; ohne Anstoss bleibt die Spalte leer, und das sieht aus "
        "wie 'wurde wieder nicht gespeichert'.")

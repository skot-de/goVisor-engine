"""Wie viele Stellen schreiben das Profil — und schreiben sie dasselbe?

⚠ WARUM DIESE DATEI EXISTIERT. Am 2026-09-17 wurde gefragt, ob es weitere Stellen gibt,
an denen zwei Vorgaenge gleichzeitig auf dasselbe Profil schreiben. Die Antwort war ja,
und der gefundene Zustand war schlimmer als ein Wettlauf:

  saveProfile (auth.ts)            Spalten + Blob   Lesen-Aendern-Schreiben
  patchProfil (unternehmen.ts)     Blob             Lesen-Aendern-Schreiben
  saveProfileFields (account.ts)   NUR Spalten      dauerhafte Spaltung
  saveIdentityCorrection           NUR company_name dauerhafte Spaltung
  api/intern/claims                NUR eine Spalte  unkritisch

`user_profiles` haelt dieselben Angaben zweimal — als Spalte und im `profile`-jsonb.
Gelesen wird fuer die Passung ausschliesslich der Blob. `/settings` schrieb nur Spalten:
wer dort seine Wertspanne aenderte, schrieb in Felder, die kein Treffer je ansieht,
waehrend die Seite meldete „wirkt beim naechsten Laden auf die Relevanz".

Nachgewiesen an der Datenbank, nicht nur am Quelltext: ein Profil trug in den Spalten
2.000.000 / 10.000.000 und im Blob null / null.
"""
import shutil
import subprocess
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
SONDE = WURZEL / "web" / "scripts" / "pruefe-profilschreiber.mjs"


def test_die_sonde_laeuft_gruen():
    """Genau eine Stelle schreibt den Blob, und der Patch ist minimal.

    ⚠ Spalten-Updates sind ausdruecklich erlaubt: sie sind einwertig und lesen nicht
    vorher, es entsteht also kein Fenster. Der BLOB ist das Problem.

    Gegengeprueft am 2026-09-17: rot, wenn (a) ein zweiter Blob-Schreiber auftaucht,
    (b) /settings wieder an `saveProfile` vorbeischreibt, (c) der Rueckfall auf
    Lesen-Aendern-Schreiben still wird, (d) `geaenderteFelder` den ganzen Blob liefert
    statt nur der Aenderung.
    """
    if not shutil.which("node"):
        return
    r = subprocess.run(["node", str(SONDE)], capture_output=True, text=True, cwd=WURZEL)
    assert r.returncode == 0, r.stdout[-1200:] + r.stderr[-400:]
    assert "Ein Schreibweg, beide Formen bedient" in r.stdout


def test_die_migration_liegt_bereit():
    """Der Merge gehoert in die Datenbank, sonst bleibt das Fenster offen.

    Eingespielt am 2026-09-17 mit `python3 scripts/migrate.py`. Gegen die Datenbank
    geprueft (Transaktion mit Ruecknahme): der Patch setzt `volMin`, waehrend `cpvFields`
    mit allen sechs Eintraegen stehen bleibt.

    ⚠ Der Rueckfall in `mischeProfilBlob` bleibt trotzdem noetig — eine frische Umgebung
    ohne diese Migration muss speichern koennen, und zwar hoerbar.
    """
    sql = WURZEL / "supabase" / "0020_profil_atomar_mischen.sql"
    assert sql.exists(), "Migration fehlt — der atomare Merge hat keine Grundlage"
    text = sql.read_text(encoding="utf-8")
    assert "create or replace function public.merge_profile" in text
    # security invoker, damit RLS weiter greift: die Zeile gehoert dem aufrufenden Nutzer.
    assert "security invoker" in text, "ohne `security invoker` umginge die Funktion RLS"
    assert "auth.uid()" in text, "ohne `auth.uid()` schriebe die Funktion fremde Zeilen"

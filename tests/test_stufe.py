"""Stufenabbildung der Paywall (`web/lib/stufeZuTier.js`, `supabase/0028`).

Vier Stufen (Preismodell v1.9 §2) auf die zwei Ebenen der Redaktion. Diese Abbildung
entscheidet, ob echte Premium-Werte den Server verlassen — und sie hat diese Entscheidung
schon einmal verloren: bis 2026-08-22 stand in `tier.ts` ein `select("tier")` auf eine
Spalte, die es in keiner Migration gab. Der catch machte daraus lautlos „free".

Am 2026-10-01 ist die Quelle von `user_profiles.plan` auf `organizations.tier` gewandert
(Sven: „tier gehoert nur an die organisation"). Derselbe Fehler kann damit erneut passieren,
nur mit einer anderen Spalte.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SONDE = WURZEL / "web" / "scripts" / "pruefe-stufe.mjs"
LOGIK = WURZEL / "web" / "lib" / "stufeZuTier.js"


def test_die_abbildung_faellt_im_zweifel_zu():
    """Faehrt die ECHTE `stufeZuTier`-Funktion, nicht ihren Quelltext.

    ⚠ Eine Wortpruefung ist hier besonders wertlos: `tier.ts` ERWAEHNT die alte Quelle
    `user_profiles.plan` in seinen Kommentaren, eine Regex darauf schlaegt also an der
    Begruendung an statt am Code. Genau daran ist `test_kuendigung_sperrt_nicht_sofort`
    am 2026-10-01 gescheitert — er prueffte eine Zeichenkette, die der Umbau ersetzt hat,
    obwohl das geprueffte VERHALTEN unveraendert war.
    """
    if not shutil.which("node"):
        return
    r = subprocess.run(["node", str(SONDE)], capture_output=True, text=True, cwd=WURZEL)
    assert r.returncode == 0, r.stdout[-900:] + r.stderr[-400:]
    assert "faellt im Zweifel zu" in r.stdout


def test_die_sonde_wird_rot_wenn_die_paywall_aufgeht():
    """Gegenprobe: ein Waechter, der nie rot werden kann, ist keiner.

    Entfernt wird der Riegel gegen UNBEKANNTE Stufen — die naheliegendste Fehlimplementierung
    und die einzige, die eine Paywall still oeffnet (ein Tippfehler in 'analyse' wuerde sonst
    Vollzugang geben).
    """
    if not shutil.which("node"):
        return
    original = LOGIK.read_text(encoding="utf-8")
    anker = '  return "free";                                   // \'free\' und alles Unbekannte'
    assert anker in original, "der Riegel steht nicht mehr da, wo der Test ihn sucht"
    try:
        LOGIK.write_text(original.replace(anker, '  return "pro";'), encoding="utf-8")
        r = subprocess.run(["node", str(SONDE)], capture_output=True, text=True, cwd=WURZEL)
        assert r.returncode != 0, "die Sonde blieb gruen, obwohl die Paywall offen stand:\n" + r.stdout[-600:]
    finally:
        LOGIK.write_text(original, encoding="utf-8")


def test_die_migration_raet_keine_bezahlte_stufe():
    """`plan='paid'` sagt NICHT, welche bezahlte Stufe gemeint ist.

    Die Unterscheidung analyse/strategie gab es bis v1.6 nicht. Gemessen am 2026-10-01 waren
    alle 15 Organisationen `free`, der Backfill musste also nichts raten. Zahlt aber jemand
    zwischen heute und dem Einspielen, darf 0028 nicht still `analyse` vergeben: das waere
    entweder ein unbezahltes Recht oder ein bezahltes, das der Kunde nicht bekommt.
    """
    sql = (WURZEL / "supabase" / "0028_tier_an_der_organisation.sql").read_text(encoding="utf-8")
    ohne_kommentar = "\n".join(z for z in sql.splitlines() if not z.strip().startswith("--"))
    assert "raise exception" in ohne_kommentar, "0028 bricht bei bezahlten Konten nicht ab"
    assert "plan <> 'free'" in ohne_kommentar, "0028 prueft die bezahlten Konten nicht"

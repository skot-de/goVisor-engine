"""Trifft `web/lib/redact.ts` die Stufen aus §3 des Preismodells?

⚠ FUER DIESE DATEI GAB ES BIS ZUM 2026-10-01 KEINEN TEST — und sie entscheidet, ob echte
Analytik-Werte den Server verlassen (CSS-Blur allein ist per DevTools lesbar,
docs/security-review.md). Sie hat in dieser Zeit zwei Befunde ueberlebt, ohne dass etwas
anschlug:

  1. Viermal `if (tier === "pro") return …` — EINE Schwelle fuer ZWEI bezahlte Stufen. Wer
     Analyse fuer 99 € kaufte, bekam Strategie fuer 349 € mit (§3.6: ganzer Bereich `++`,
     „keine Ausnahme").
  2. `redactFirma` schuetzte nur `expiring`, obwohl §3.5 fuenf Dinge dem `++`-Tab
     „Angriffspunkte" zuordnet. `sits` und `signale` verliessen den Server auf JEDER Stufe.

Die Sonde faehrt die ECHTE Datei (Node 25 kann TypeScript; nur zwei Importe werden fuer den
Lauf umgeschrieben, der Rumpf bleibt unveraendert).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SONDE = WURZEL / "web" / "scripts" / "pruefe-redaktion.mjs"
REDACT = WURZEL / "web" / "lib" / "redact.ts"


def _fahre() -> subprocess.CompletedProcess:
    return subprocess.run(["node", str(SONDE)], capture_output=True, text=True, cwd=WURZEL)


def test_die_redaktion_trifft_die_stufen():
    if not shutil.which("node"):
        return
    r = _fahre()
    assert r.returncode == 0, r.stdout[-1200:] + r.stderr[-400:]
    assert "Redaktion trifft die Stufen" in r.stdout


def test_die_sonde_findet_die_rueckkehr_der_einen_schwelle():
    """Gegenprobe 1: eine Schwelle fuer beide bezahlten Stufen — der Befund, der 250 € je
    Kunde und Monat verschenkte."""
    if not shutil.which("node"):
        return
    original = REDACT.read_text(encoding="utf-8")
    i = original.index("export function redactStrategie(")
    kaputt = original[:i] + original[i:].replace("darfStrategie(tier)", "darfAnalyse(tier)", 1)
    assert kaputt != original, "die Schwelle steht nicht mehr da, wo der Test sie sucht"
    try:
        REDACT.write_text(kaputt, encoding="utf-8")
        r = _fahre()
        assert r.returncode != 0, "die Sonde blieb gruen, obwohl Analyse die ++-Inhalte sah"
        assert "§3.6" in r.stdout + r.stderr
    finally:
        REDACT.write_text(original, encoding="utf-8")


def test_die_sonde_findet_die_luecke_bei_den_angriffspunkten():
    """Gegenprobe 2: nur `expiring` geschuetzt, `sits` und `signale` offen — der Zustand bis
    zum 2026-10-01, den der Kommentar dort ausdruecklich als Absicht nannte."""
    if not shutil.which("node"):
        return
    original = REDACT.read_text(encoding="utf-8")
    anker = '  d.sits = [];                       // ++ „Wo festsitzt"'
    assert anker in original, "die sits-Zeile steht nicht mehr da, wo der Test sie sucht"
    i = original.index(anker)
    j = original.index("  return d;", i)
    kaputt = original[:i] + "  d.expiring = [];\n" + original[j:]
    try:
        REDACT.write_text(kaputt, encoding="utf-8")
        r = _fahre()
        assert r.returncode != 0, "die Sonde blieb gruen, obwohl sits und signale offen lagen"
        aus = r.stdout + r.stderr
        assert "Wo festsitzt" in aus and "Weitere Signale" in aus
    finally:
        REDACT.write_text(original, encoding="utf-8")


def test_die_uebersicht_wird_nicht_mitredigiert():
    """⚠ Eine Redaktion, die ZU VIEL nimmt, ist genauso ein Fehler. §3.5 ordnet Kennzahlen,
    Leistungsfelder und Regionen der „Uebersicht" (`+`) zu — und der Zaehler
    `kpi.aus18_n` ist der entworfene Teaser zur `++`-Liste, nicht ein Leck."""
    if not shutil.which("node"):
        return
    r = _fahre()
    assert r.returncode == 0, r.stdout[-900:]
    assert "Uebersicht" in r.stdout or "27 Pruefungen" in r.stdout

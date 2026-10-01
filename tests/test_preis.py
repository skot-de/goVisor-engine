"""Trifft der Erweiterungspreis §5.2 des Preismodells?

⚠ `web/lib/preise.ts` stand bis zum 2026-10-01 auf `0`, mit der Begruendung „das Kostenmodell
ist offen (Sven, 2026-09-30)". v1.9 traegt genau dieses Datum und legt 29 €/Mon · 299 €/Jahr
fest — die Datei wurde geschrieben, BEVOR die Entscheidung im Dokument stand, und niemand hat
sie nachgezogen. Die Umgebungsvariablen waren nirgends gesetzt, weder in `.env.local` noch
dokumentiert, und jeder Kauf scheiterte an einer Meldung, die auf das falsche Hindernis zeigte.

Sven am 2026-10-01: „warum ist der seat und profil preis nicht gesetzt? der steht doch im
dokument, ich meine 29euro."

⛔ Der gesetzte Preis ERMOEGLICHT KEINEN KAUF. `/api/kauf/checkout` antwortet weiter mit 503,
nur an der richtigen Stelle: Stripe ist nicht konfiguriert und die Checkout-Session ist nicht
implementiert. Der Preis war das erste von drei Hindernissen.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SONDE = WURZEL / "web" / "scripts" / "pruefe-preis.mjs"
PREISE = WURZEL / "web" / "lib" / "preise.ts"


def _fahre() -> subprocess.CompletedProcess:
    return subprocess.run(["node", str(SONDE)], capture_output=True, text=True, cwd=WURZEL)


def test_der_preis_trifft_die_tafel():
    if not shutil.which("node"):
        return
    r = _fahre()
    assert r.returncode == 0, r.stdout[-900:] + r.stderr[-400:]
    assert "trifft §5.2" in r.stdout


def test_die_sonde_findet_zwei_getrennte_preise():
    """Gegenprobe 1: §5.2 sagt „weiterer Nutzer ODER weiteres Unternehmensprofil" zum gleichen
    Preis. Zwei getrennte Preise waren die Tafel von v1.7 und genau der Rueckfall, der still
    passiert, wenn jemand die alte Form wiederherstellt."""
    if not shutil.which("node"):
        return
    original = PREISE.read_text(encoding="utf-8")
    anker = "  void art;\n  return ERWEITERUNG_CENTS[takt];"
    assert anker in original, "die Preisfunktion steht nicht mehr da, wo der Test sie sucht"
    kaputt = original.replace(
        anker, '  return art === "profile" ? ERWEITERUNG_CENTS[takt] + 1000 : ERWEITERUNG_CENTS[takt];', 1)
    try:
        PREISE.write_text(kaputt, encoding="utf-8")
        r = _fahre()
        assert r.returncode != 0, "die Sonde blieb gruen bei zwei verschiedenen Preisen"
        assert "eine Position" in r.stdout + r.stderr
    finally:
        PREISE.write_text(original, encoding="utf-8")


def test_die_sonde_findet_einen_geratenen_jahrespreis():
    """Gegenprobe 2: §13 verlangt Jahrespreis = 10,25 × Monat, aufgerundet auf 9er-Endung.
    300 € sieht runder aus als 299 € und waere falsch."""
    if not shutil.which("node"):
        return
    original = PREISE.read_text(encoding="utf-8")
    assert "?? 29900" in original, "der Jahrespreis steht nicht mehr da, wo der Test ihn sucht"
    try:
        PREISE.write_text(original.replace("?? 29900", "?? 30000", 1), encoding="utf-8")
        r = _fahre()
        assert r.returncode != 0, "die Sonde blieb gruen bei einem geratenen Jahrespreis"
        assert "9er-Endung" in r.stdout + r.stderr
    finally:
        PREISE.write_text(original, encoding="utf-8")


def test_der_kaufpfad_bleibt_ein_ehrlicher_stub():
    """⚠ Der gesetzte Preis darf NICHT als Kaufmoeglichkeit erscheinen. Der Checkout muss
    weiter 503 liefern, solange Stripe nicht konfiguriert und die Session nicht gebaut ist —
    ein vorgetaeuschter Erfolg waere schlimmer als die Absage."""
    route = (WURZEL / "web" / "app" / "api" / "kauf" / "checkout" / "route.ts").read_text(encoding="utf-8")
    ohne_kommentar = "\n".join(z.split("//")[0] for z in route.splitlines())
    assert "stripeEnabled" in ohne_kommentar, "der Stripe-Riegel ist weg"
    assert "503" in ohne_kommentar, "der Checkout meldet keinen Stub mehr"

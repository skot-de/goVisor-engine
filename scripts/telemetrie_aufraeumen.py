#!/usr/bin/env python3
"""Telemetrie-Ereignisse aelter als N Tage loeschen (Vorgabe 180).

    python3 scripts/telemetrie_aufraeumen.py [--tage 180] [--probe]

WARUM DAS EIN EIGENER SCHRITT IM NACHTLAUF IST. Speicherbegrenzung ist keine Hausordnung,
sondern Pflicht (DSGVO Art. 5 Abs. 1 lit. e): personenbezogene Daten duerfen nur so lange
liegen, wie sie gebraucht werden. Die Funktion `gov_ereignisse_aufraeumen` steht seit 0035 in
der Datenbank, aber sie raeumt NICHT von selbst — Postgres hat keinen Zeitgeber. Ohne diesen
Aufruf sammelt die Tabelle unbegrenzt, und niemand merkt es, weil nichts kaputtgeht.

⚠ GENAU DIESE FEHLERKLASSE heisst hier „gebaut, nicht verdrahtet", und die Telemetrie ist
schon einmal daran gescheitert: `web/lib/analytics.ts` feuerte seit Ticket #8 neun Ereignisse
in einen Ring-Puffer, weil die Senke nie angeschlossen wurde. Deshalb prueft
`tests/test_telemetrie.py`, dass dieser Aufruf im Nachtlauf steht.

⚠ 180 Tage sind eine Abwaegung, keine Norm: Trichter-Quoten will man ueber ein Jahr
vergleichen koennen, Rohklicks braucht nach einem halben Jahr niemand mehr. Wer die Zahl
aendert, aendert eine Datenschutz-Aussage — dann gehoert die Datenschutzerklaerung mit
angepasst.
"""
import argparse
import json
import pathlib
import subprocess
import sys

WURZEL = pathlib.Path(__file__).resolve().parent.parent
GEHEIM = WURZEL / ".secrets" / "supabase.txt"


def zugang() -> tuple[str, str]:
    """URL und Service-Schluessel aus `.secrets/supabase.txt` (zwei Zeilen)."""
    if not GEHEIM.exists():
        sys.exit(f"{GEHEIM.relative_to(WURZEL)} fehlt — ohne Service-Schluessel kein Aufraeumen.")
    zeilen = [z.strip() for z in GEHEIM.read_text(encoding="utf-8").splitlines() if z.strip()]
    if len(zeilen) < 2:
        sys.exit(f"{GEHEIM.relative_to(WURZEL)} braucht zwei Zeilen: URL, dann Schluessel.")
    return zeilen[0].rstrip("/"), zeilen[1]


def hole(args: list[str]) -> tuple[str, str]:
    """curl aufrufen, (Koerper, HTTP-Code) zurueckgeben.

    ⚠ **curl statt urllib** — dasselbe Muster und derselbe Grund wie in
    `export_supabase.py:184`: das python.org-Python auf dieser Maschine hat keine
    CA-Bundle-Anbindung und scheitert mit `SSL: CERTIFICATE_VERIFY_FAILED`. Die Pruefung
    abzuschalten waere die falsche Antwort — dann redet das Skript mit jedem, der sich fuer
    Supabase ausgibt, und es traegt einen Service-Schluessel bei sich.
    """
    out = subprocess.run(["curl", "-sS", "--max-time", "120", "-w", "%{http_code}", *args],
                         capture_output=True, text=True)
    koerper = out.stdout.strip()
    code = koerper[-3:] if koerper[-3:].isdigit() else "???"
    return koerper[:-3], code


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tage", type=int, default=180)
    ap.add_argument("--probe", action="store_true",
                    help="nur zaehlen, was faellig waere, nichts loeschen")
    a = ap.parse_args()

    url, key = zugang()
    kopf = ["-H", f"apikey: {key}", "-H", f"Authorization: Bearer {key}",
            "-H", "Content-Type: application/json"]

    if a.probe:
        # ⚠ Zaehlen statt loeschen: `count=exact` ueber denselben Zeitfilter, den die Funktion
        #   benutzt. Eine Probe mit anderer Grenze misst etwas anderes als der Lauf und ist
        #   damit schlimmer als keine.
        from datetime import datetime, timedelta, timezone
        # ⚠ `Z` statt `+00:00`. `isoformat()` haengt die Zone als `+00:00` an, und ein `+` im
        #   Query-String bedeutet ein LEERZEICHEN — PostgREST bekam dadurch einen kaputten
        #   Zeitstempel und antwortete mit HTTP 400. Fehler kostete genau einen Lauf.
        grenze = (datetime.now(timezone.utc) - timedelta(days=max(a.tage, 1))
                  ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        koerper, code = hole([
            f"{url}/rest/v1/gov_ereignisse?select=id&erfasst_at=lt.{grenze}&limit=1",
            *kopf, "-H", "Prefer: count=exact", "-D", "-"])
        if code != "200":
            print(f"  ⚠ Probe fehlgeschlagen: HTTP {code} {koerper[:200]!r}")
            return 1
        bereich = next((z.split("/")[-1].strip() for z in koerper.splitlines()
                        if z.lower().startswith("content-range:")), "?")
        print(f"  Probe: {bereich} Ereignisse aelter als {a.tage} Tage (nichts geloescht)")
        return 0

    koerper, code = hole([f"{url}/rest/v1/rpc/gov_ereignisse_aufraeumen", "-X", "POST",
                          *kopf, "--data-binary", json.dumps({"tage": a.tage})])
    if code != "200":
        # Fail-open im Nachtlauf: ein nicht geraeumtes Protokoll ist ein Mangel, aber kein
        # Grund, den restlichen Lauf abzubrechen. Laut genug, damit es auffaellt.
        print(f"  ⚠ Aufraeumen fehlgeschlagen: HTTP {code} {koerper[:200]!r}")
        return 1
    print(f"  ✓ {koerper.strip() or 0} Telemetrie-Ereignisse aelter als {a.tage} Tage geloescht")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

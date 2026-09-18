#!/usr/bin/env python3
"""Ein Konto zum PRUEFEN — angemeldete Routen ohne Browser erreichbar machen.

⚠ WARUM ES DAS GIBT. `/api/leads`, `/api/doc-analysis` und `/api/lead-detail` liegen
hinter dem Anmeldetor in `web/middleware.ts` und antworten ohne Sitzung mit 401. Am
2026-09-17 blieb deshalb eine Aenderung an `/api/leads` ungebaut, obwohl sie gemessen
48 % Uebertragung gespart haette: eine Komprimierungsaenderung an der wichtigsten Route
ungeprueft auszuliefern waere die falsche Wette — setzt Next seinen gzip zusaetzlich
darueber, ist die Antwort doppelt kodiert und die Liste fuer JEDEN kaputt.

⚠ KEINE MAIL. `POST /auth/v1/admin/users` mit `email_confirm: true` legt das Konto an,
ohne etwas zu verschicken — dieselbe Mechanik wie `scripts/demo_konto.py`. Ein
Pruefwerkzeug, das Post an echte Adressen ausloest, waere das erste, was schiefgeht.

⚠ DAS KONTO IST LEER. Es bekommt KEIN Profil: geprueft werden Routen, nicht Treffer.
Ein Pruefkonto mit Profil saehe aus wie ein Nutzer und wuerde irgendwann fuer einen
gehalten.

    python3 scripts/pruefkonto.py            anlegen (oder Passwort neu setzen)
    python3 scripts/pruefkonto.py --loeschen wieder weg
"""
from __future__ import annotations

import argparse
import re
import secrets
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
# ⚠ `.invalid` ist per RFC 2606 dauerhaft nicht aufloesbar. Selbst wenn jemand die
# Mailsperre umgeht, kann an diese Adresse nichts zugestellt werden.
ADRESSE = "pruef@govisor.invalid"
PASSWORT_DATEI = ROOT / ".secrets" / "pruefkonto.txt"


def env() -> dict[str, str]:
    e: dict[str, str] = {}
    for datei in ("web/.env.local", ".env"):
        p = ROOT / datei
        if not p.exists():
            continue
        for zeile in p.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*([A-Za-z_]+)\s*=\s*\"?([^\"\n]*)\"?", zeile)
            if m:
                e.setdefault(m.group(1), m.group(2))
    return e


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--loeschen", action="store_true")
    a = ap.parse_args(argv)

    e = env()
    url = e.get("NEXT_PUBLIC_SUPABASE_URL", "").strip().rstrip("/")
    key = e.get("SUPABASE_SECRET_KEY", "").strip()
    if not url or not key:
        sys.exit("  ✖ NEXT_PUBLIC_SUPABASE_URL oder SUPABASE_SECRET_KEY fehlt in web/.env.local")
    kopf = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    # ⚠ Dieselbe Sperre wie in `demo_konto.py`: ein Werkzeug, das Konten loescht, darf die
    # Adressen der Betreiber nie anfassen — auch nicht, wenn jemand ADRESSE umschreibt.
    geschuetzt = {x.strip().lower() for x in e.get("ADMIN_EMAILS", "").split(",") if x.strip()}
    if ADRESSE.lower() in geschuetzt:
        sys.exit(f"  ⛔ {ADRESSE} steht in ADMIN_EMAILS — wird nicht angefasst.")

    r = requests.get(f"{url}/auth/v1/admin/users", headers=kopf,
                     params={"page": 1, "per_page": 200}, timeout=30)
    r.raise_for_status()
    vorhanden = next((u for u in r.json().get("users", [])
                      if (u.get("email") or "").lower() == ADRESSE), None)

    if a.loeschen:
        if not vorhanden:
            print(f"  {ADRESSE} gibt es nicht — nichts zu tun.")
            return 0
        d = requests.delete(f"{url}/auth/v1/admin/users/{vorhanden['id']}", headers=kopf, timeout=30)
        if not d.ok:
            sys.exit(f"  ✖ Loeschen fehlgeschlagen: {d.status_code} {d.text[:200]}")
        PASSWORT_DATEI.unlink(missing_ok=True)
        print(f"  {ADRESSE} geloescht.")
        return 0

    passwort = secrets.token_urlsafe(24)
    if vorhanden:
        u = requests.put(f"{url}/auth/v1/admin/users/{vorhanden['id']}", headers=kopf,
                         json={"password": passwort, "email_confirm": True}, timeout=30)
        if not u.ok:
            sys.exit(f"  ✖ Passwort nicht gesetzt: {u.status_code} {u.text[:200]}")
        print(f"  {ADRESSE} gab es schon — Passwort neu gesetzt.")
    else:
        c = requests.post(f"{url}/auth/v1/admin/users", headers=kopf,
                          json={"email": ADRESSE, "password": passwort,
                                "email_confirm": True}, timeout=30)
        if not c.ok:
            sys.exit(f"  ✖ Konto nicht angelegt: {c.status_code} {c.text[:200]}")
        print(f"  {ADRESSE} angelegt (ohne Mailversand).")

    PASSWORT_DATEI.parent.mkdir(parents=True, exist_ok=True)
    PASSWORT_DATEI.write_text(passwort + "\n", encoding="utf-8")
    PASSWORT_DATEI.chmod(0o600)
    print(f"  Passwort in {PASSWORT_DATEI.relative_to(ROOT)} (nur fuer den Besitzer lesbar).")
    print("\n  Angemeldete Anfrage:")
    print("    C=$(node web/scripts/pruefanmeldung.mjs "
          f"{ADRESSE} \"$(cat {PASSWORT_DATEI.relative_to(ROOT)})\" 2>/dev/null)")
    print('    curl -s -b "$C" "http://127.0.0.1:3000/api/leads?branche=bau" -o /dev/null -w "%{http_code}\\n"')
    return 0


if __name__ == "__main__":
    sys.exit(main())

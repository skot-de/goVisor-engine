#!/usr/bin/env python3
"""Ein ADMIN-Konto zum Pruefen der internen Seiten (/intern) — ohne Browser-Login, ohne
fremdes Passwort.

⚠ WARUM GETRENNT VON `pruefkonto.py`. Das gewoehnliche Pruefkonto darf ausdruecklich NICHTS
anfassen, was in `ADMIN_EMAILS` steht (Schutz der Betreiber-Adressen). Fuer `/intern` ist aber
GENAU das noetig: die Middleware laesst nur durch, wessen E-Mail in `ADMIN_EMAILS` steht
(`web/lib/admin.ts`). Dieses Werkzeug legt deshalb eine EIGENE Wegwerf-Adresse an und traegt
sie lokal in `ADMIN_EMAILS` ein — aber es fasst die menschlichen Admin-Adressen nie an.

⚠ KEINE MAIL, `.invalid`-Adresse (RFC 2606, nie zustellbar). `POST /auth/v1/admin/users` mit
`email_confirm: true` legt an, ohne etwas zu verschicken (wie `pruefkonto.py`/`demo_konto.py`).

⚠ NUR LOKAL GEDACHT. Es editiert `web/.env.local`; in der Produktion steht `ADMIN_EMAILS` in
der Deploy-Umgebung, nicht in dieser Datei. Nach dem Anlegen/Loeschen muss der Dev-Server neu
starten, damit er das geaenderte `ADMIN_EMAILS` liest.

    python3 scripts/pruefkonto_admin.py            anlegen (+ in ADMIN_EMAILS eintragen)
    python3 scripts/pruefkonto_admin.py --status   nur nachsehen
    python3 scripts/pruefkonto_admin.py --loeschen  Konto weg + aus ADMIN_EMAILS raus
"""
from __future__ import annotations

import argparse
import re
import secrets
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
ADRESSE = "pruef-admin@govisor.invalid"
PASSWORT_DATEI = ROOT / ".secrets" / "pruefkonto_admin.txt"
ENV_DATEI = ROOT / "web" / ".env.local"
# Niemals anfassen — egal was ADRESSE sagt. Die echten Betreiber-Konten.
MENSCHEN = {"sk@skot.de", "sven.kotzur@gmail.com"}


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


def admin_emails_setzen(drin: bool) -> bool:
    """ADRESSE in web/.env.local ADMIN_EMAILS ein-/austragen. True, wenn sich etwas aenderte."""
    if not ENV_DATEI.exists():
        sys.exit(f"  ✖ {ENV_DATEI} fehlt.")
    zeilen = ENV_DATEI.read_text(encoding="utf-8").splitlines()
    for i, z in enumerate(zeilen):
        m = re.match(r"(\s*ADMIN_EMAILS\s*=\s*)\"?([^\"\n]*)\"?\s*$", z)
        if not m:
            continue
        liste = [x.strip() for x in m.group(2).split(",") if x.strip()]
        hat = ADRESSE in liste
        if drin and not hat:
            liste.append(ADRESSE)
        elif not drin and hat:
            liste = [x for x in liste if x != ADRESSE]
        else:
            return False
        zeilen[i] = f"{m.group(1)}{','.join(liste)}"
        ENV_DATEI.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
        return True
    # Keine ADMIN_EMAILS-Zeile gefunden
    if drin:
        zeilen.append(f"ADMIN_EMAILS={ADRESSE}")
        ENV_DATEI.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
        return True
    return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--loeschen", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args(argv)

    if ADRESSE.lower() in MENSCHEN:
        sys.exit("  ⛔ ADRESSE ist eine echte Betreiber-Adresse — abgebrochen.")

    e = env()
    url = e.get("NEXT_PUBLIC_SUPABASE_URL", "").strip().rstrip("/")
    key = e.get("SUPABASE_SECRET_KEY", "").strip()
    if not url or not key:
        sys.exit("  ✖ NEXT_PUBLIC_SUPABASE_URL oder SUPABASE_SECRET_KEY fehlt in web/.env.local")
    kopf = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    r = requests.get(f"{url}/auth/v1/admin/users", headers=kopf,
                     params={"page": 1, "per_page": 200}, timeout=30)
    r.raise_for_status()
    vorhanden = next((u for u in r.json().get("users", [])
                      if (u.get("email") or "").lower() == ADRESSE), None)

    if a.status:
        in_env = ADRESSE in {x.strip() for x in e.get("ADMIN_EMAILS", "").split(",")}
        print(f"  Konto:        {'vorhanden' if vorhanden else 'fehlt'}")
        print(f"  ADMIN_EMAILS: {'enthaelt ' + ADRESSE if in_env else 'ohne ' + ADRESSE}")
        print(f"  Passwort:     {'in ' + str(PASSWORT_DATEI.relative_to(ROOT)) if PASSWORT_DATEI.exists() else 'keine Datei'}")
        return 0

    if a.loeschen:
        if vorhanden:
            d = requests.delete(f"{url}/auth/v1/admin/users/{vorhanden['id']}", headers=kopf, timeout=30)
            if not d.ok:
                sys.exit(f"  ✖ Loeschen fehlgeschlagen: {d.status_code} {d.text[:200]}")
            print(f"  {ADRESSE} geloescht.")
        else:
            print(f"  {ADRESSE} gab es nicht.")
        PASSWORT_DATEI.unlink(missing_ok=True)
        if admin_emails_setzen(drin=False):
            print("  Aus ADMIN_EMAILS (web/.env.local) entfernt — Dev-Server neu starten.")
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
                          json={"email": ADRESSE, "password": passwort, "email_confirm": True}, timeout=30)
        if not c.ok:
            sys.exit(f"  ✖ Konto nicht angelegt: {c.status_code} {c.text[:200]}")
        print(f"  {ADRESSE} angelegt (ohne Mailversand).")

    PASSWORT_DATEI.parent.mkdir(parents=True, exist_ok=True)
    PASSWORT_DATEI.write_text(passwort + "\n", encoding="utf-8")
    PASSWORT_DATEI.chmod(0o600)
    print(f"  Passwort in {PASSWORT_DATEI.relative_to(ROOT)} (nur fuer den Besitzer lesbar).")
    if admin_emails_setzen(drin=True):
        print("  In ADMIN_EMAILS (web/.env.local) eingetragen — Dev-Server NEU STARTEN, dann wirkt es.")
    else:
        print("  Stand schon in ADMIN_EMAILS.")
    print("\n  Smoke-Test danach:")
    print("    node web/scripts/intern_smoke.mjs")
    return 0


if __name__ == "__main__":
    sys.exit(main())

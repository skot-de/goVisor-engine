#!/usr/bin/env python3
"""Erzeugt einen Anmeldelink, OHNE eine Mail zu verschicken.

**Wofür.** Der eingebaute Mailversand von Supabase ist auf wenige Mails pro Stunde
gedrosselt. Beim Entwickeln und beim Vorführen ist das die falsche Bremse: man braucht eine
Sitzung, nicht ein Postfach. Sven am 2026-08-18, nachdem er ins Limit lief: „email rate
limit.. ich muss warten." Muss er nicht.

Der Admin-Endpunkt ``/auth/v1/admin/generate_link`` erzeugt denselben Token, den auch die
Mail tragen würde, verschickt aber nichts. Wir bauen daraus die Adresse unserer eigenen
Rückkehr-Route.

**Warum ``token_hash`` und nicht der fertige ``action_link``.** Der ``action_link`` führt
über Supabase und endet im PKCE-Weg mit ``?code=`` — der funktioniert nur in dem Browser,
der die Anfrage gestellt hat, und hier hat ihn niemand gestellt. ``token_hash`` braucht
keinen Prüfschlüssel und trägt deshalb in jedem Browser, auch auf dem Telefon.

⚠️ **Der ausgegebene Link IST die Anmeldung.** Er gilt eine Stunde und genau einmal. Nicht
in ein Ticket kleben, nicht weiterschicken. Wer ihn hat, ist drin.

⚠️ Nur für eigene Konten auf der eigenen Instanz. Das Skript braucht den Secret Key aus
``web/.env.local``; wo der Key nicht hingehört, gehört dieses Skript auch nicht hin.

Aufruf::

    python3 scripts/anmeldelink.py                      # Adresse aus ADMIN_EMAILS
    python3 scripts/anmeldelink.py name@firma.de
    python3 scripts/anmeldelink.py name@firma.de --ziel /intern/lauf
    python3 scripts/anmeldelink.py name@firma.de --basis https://govisor.eu
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ⚠ `requests` und NICHT `urllib`. Das python.org-Python auf macOS bringt keinen
# Zertifikatsspeicher mit; `urllib` scheitert dort an jeder HTTPS-Verbindung mit
# CERTIFICATE_VERIFY_FAILED, was wie ein Netzproblem aussieht und keines ist. `requests`
# bringt certifi mit und wird im Rest des Projekts aus genau diesem Grund benutzt
# (`govisor/bulk.py`, `scripts/probe_portals.py`).
import requests

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / "web/.env.local"


def env() -> dict[str, str]:
    if not ENV.exists():
        sys.exit(f"  ✖ {ENV} fehlt.")
    return dict(re.findall(r"^([A-Z_]+)\s*=\s*(.*)$", ENV.read_text(encoding="utf-8"), re.M))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("email", nargs="?", help="Konto; ohne Angabe die erste Adresse aus ADMIN_EMAILS")
    ap.add_argument("--ziel", default="/leads", help="wohin nach dem Anmelden (Vorgabe: /leads)")
    ap.add_argument("--basis", default="http://localhost:3000", help="Adresse der App")
    a = ap.parse_args()

    e = env()
    url = e.get("NEXT_PUBLIC_SUPABASE_URL", "").strip().rstrip("/")
    key = e.get("SUPABASE_SECRET_KEY", "").strip()
    if not url or not key:
        sys.exit("  ✖ NEXT_PUBLIC_SUPABASE_URL oder SUPABASE_SECRET_KEY fehlt in web/.env.local")

    email = a.email or e.get("ADMIN_EMAILS", "").split(",")[0].strip()
    if not email:
        sys.exit("  ✖ Keine Adresse: als Argument angeben oder ADMIN_EMAILS setzen.")

    # `magiclink` verlangt ein vorhandenes Konto, `signup` legt eines an. Erst der Normalfall,
    # dann der Rückfall — so entsteht kein Konto, wo eigentlich nur eines gesucht war.
    kopf = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    for art in ("magiclink", "signup"):
        r = requests.post(f"{url}/auth/v1/admin/generate_link",
                          json={"type": art, "email": email}, headers=kopf, timeout=30)
        if r.ok:
            d = r.json()
            break
        # 422 heisst hier „kein Konto mit dieser Adresse". Dann, und nur dann, legen wir
        # eines an — ein stiller Neuanlage-Versuch bei jedem anderen Fehler wuerde
        # Karteileichen erzeugen, waehrend die eigentliche Ursache unsichtbar bleibt.
        if art == "magiclink" and (r.status_code == 422 or "not found" in r.text.lower()):
            print(f"  Kein Konto für {email}, lege eines an.")
            continue
        sys.exit(f"  ✖ Supabase {r.status_code}: {r.text[:200]}")
    else:
        sys.exit("  ✖ Supabase hat keinen Link erzeugt.")

    hash_ = (d.get("properties") or d).get("hashed_token")
    if not hash_:
        sys.exit(f"  ✖ Kein hashed_token in der Antwort: {json.dumps(d)[:200]}")

    typ = "magiclink" if art == "magiclink" else "signup"
    ziel = a.ziel if a.ziel.startswith("/") and not a.ziel.startswith("//") else "/leads"
    print(f"\n  Anmeldelink für {email} (eine Stunde gültig, einmal verwendbar):\n")
    print(f"  {a.basis}/auth/callback?token_hash={hash_}&type={typ}&next={ziel}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

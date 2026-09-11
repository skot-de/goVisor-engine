#!/usr/bin/env python3
"""Legt ein Vorführ-Konto mit FERTIGEM Profil an und gibt den Anmeldelink aus.

    python3 scripts/demo_konto.py --firma "H. Klostermann Baugesellschaft mbH" \
                                  --email demo@klostermann-hamm.de

WOFUER. Der Weg Landingpage → Eignungs-Check → Onboarding endet an der Registrierung, und
die schickt eine Bestaetigungsmail. Vor Publikum ist das die falsche Bremse — man braucht
eine Sitzung, kein Postfach. `scripts/anmeldelink.py` loest das fuer den LOGIN; hier kommt
das Profil dazu, damit die App nicht leer aufgeht.

⚠ WAS DIESES SKRIPT ANFASST. Es legt bei Bedarf ein Konto in `auth.users` an und
ueberschreibt `public.user_profiles` fuer genau dieses Konto. Nichts sonst. Es schreibt
weder in `data/` noch in `web/data` und beruehrt keine fremden Konten.

⚠ DAS PROFIL WIRD NICHT ERFUNDEN. Firma, Identitaet, CPV-Felder und Regionen kommen aus
derselben Quelle, die auch das Onboarding benutzt (`/api/entity-search` ueber
`suppliers.json`). Ein von Hand getipptes Demo-Profil waere eine Behauptung ueber Daten,
die niemand gelesen hat — genau das, wogegen das Produkt antritt. Fehlt die Firma dort,
bricht der Lauf ab, statt etwas Plausibles einzusetzen.

⚠ DER LINK IST DIE ANMELDUNG. Eine Stunde gueltig, genau einmal. Nicht weiterschicken.

GEHT EINE MAIL AN DIE ADRESSE? NEIN — und zwar aus zwei unabhaengigen Gruenden.
  1. `POST /auth/v1/admin/users` versendet nichts. `internal/api/admin.go` im Quelltext von
     `supabase/auth` (geprueft an HEAD 4eee58f, 2026-09-09) enthaelt ueber die gesamte Datei
     KEINE Mailer-Referenz. Auch der Send-Email-Hook greift nicht: er sitzt INNERHALB von
     `sendEmail()`, und diese Funktion wird hier nie erreicht.
  2. Ohne hinterlegtes Custom SMTP verweigert Supabase seit dem 26.09.2024 die Zustellung an
     Adressen ausserhalb des Projekt-Teams („Email address not authorized").

⚠ DIE EINE LUECKE, die keiner der beiden Gruende deckt: ein selbst gebauter
`before_user_created`- oder `after_user_created`-Hook feuert beim Anlegen und koennte
seinerseits mailen — an Supabase vorbei. Das ist ueber die API nicht zuverlaessig abfragbar.
Wer dieses Skript auf eine FREMDE Adresse loslaesst, sieht vorher im Dashboard unter
Authentication > Hooks nach.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import requests                     # nicht urllib: python.org-Python hat keinen Zertspeicher

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / "web/.env.local"


def env() -> dict[str, str]:
    if not ENV.exists():
        sys.exit(f"  ✖ {ENV} fehlt.")
    return dict(re.findall(r"^([A-Z_]+)\s*=\s*(.*)$", ENV.read_text(encoding="utf-8"), re.M))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--firma", required=True, help="Name, wie ihn die Firmensuche kennt")
    ap.add_argument("--email", required=True, help="Adresse des Vorfuehr-Kontos")
    ap.add_argument("--app", default="http://localhost:3000", help="Adresse der laufenden App")
    ap.add_argument("--ziel", default="/leads", help="wohin nach dem Anmelden")
    ap.add_argument("--trocken", action="store_true", help="nur zeigen, nichts schreiben")
    a = ap.parse_args()

    e = env()
    url = e.get("NEXT_PUBLIC_SUPABASE_URL", "").strip().rstrip("/")
    key = e.get("SUPABASE_SECRET_KEY", "").strip()
    if not url or not key:
        sys.exit("  ✖ NEXT_PUBLIC_SUPABASE_URL oder SUPABASE_SECRET_KEY fehlt in web/.env.local")
    kopf = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    # ── 1. Die Firma aus der ECHTEN Suche holen ───────────────────────────────
    try:
        r = requests.get(f"{a.app}/api/entity-search", params={"q": a.firma}, timeout=30)
        r.raise_for_status()
        treffer = r.json().get("matches") or []
    except Exception as ex:
        sys.exit(f"  ✖ Firmensuche nicht erreichbar ({ex}).\n"
                 f"    Laeuft die App unter {a.app}? Ohne sie gibt es kein belegtes Profil.")
    if not treffer:
        sys.exit(f"  ✖ Die Firmensuche kennt {a.firma!r} nicht. Kein Profil ohne Beleg.")
    f = treffer[0]
    felder = f.get("fields") or []
    print(f"  Firma:      {f['name']}")
    print(f"  Identitaet: {f['id']}")
    print(f"  Belegt:     {f.get('wins')} Zuschlaege bei {f.get('buyers')} Auftraggebern, "
          f"seit {f.get('seit')}")
    for x in felder[:4]:
        print(f"                CPV {x['cpv4']} · {x['label'][:46]} ({x['wins']})")
    if len(treffer) > 1:
        print(f"  ⚠ {len(treffer)} Treffer — genommen wird der erste. Die uebrigen: "
              f"{', '.join(t['name'][:28] for t in treffer[1:4])}")

    if a.trocken:
        print("\n  (trocken — nichts geschrieben)")
        return 0

    # ── 2. Konto anlegen — auf dem nachweislich mailfreien Weg ────────────────
    #
    # ⚠ WARUM `admin/users` UND NICHT `admin/generate_link`. Beide verschicken nichts, aber
    # der Beleg ist ungleich stark. `internal/api/admin.go` (supabase/auth) enthaelt ueber
    # die GESAMTE Datei KEINE einzige Mailer-Referenz — fuer keinen ihrer 13 Handler. Bei
    # `generate_link` muesste man dagegen die Abwesenheit eines `sendEmail`-Aufrufs
    # innerhalb eines 260-Zeilen-Handlers argumentieren. Wenn eine fremde Firmenadresse im
    # Spiel ist, nimmt man das staerkere Argument.
    #
    # ⚠ UND EINE FALLE IN `generate_link`: `type=magiclink` auf eine NICHT existierende
    # Adresse wird still zu `signup` umgeschrieben und legt den Nutzer an — mit einem
    # zufaelligen Passwort. Ein Aufruf, von dem man nur einen Link erwartet, schreibt dann.
    #
    # ⛔ NIEMALS `admin/invite` oder `inviteUserByEmail`: die verschicken tatsaechlich.
    # Im Dashboard ist das der Knopf „Invite user" — er liegt direkt neben „Add user".
    import secrets

    such = requests.get(f"{url}/auth/v1/admin/users", headers=kopf,
                        params={"page": 1, "per_page": 200}, timeout=30)
    vorhanden = None
    if such.ok:
        for u in (such.json().get("users") or []):
            if (u.get("email") or "").lower() == a.email.lower():
                vorhanden = u
                break

    if vorhanden:
        user_id = vorhanden["id"]
        print(f"\n  Konto {a.email} existiert bereits ({user_id[:8]}…), lege keines an.")
    else:
        r = requests.post(f"{url}/auth/v1/admin/users", headers=kopf, timeout=30, json={
            "email": a.email,
            # Ohne `email_confirm` entstuende ein totes Konto, das sich nicht anmelden kann.
            # Das Flag setzt nur `email_confirmed_at` in der Datenbank — es loest nichts aus.
            "email_confirm": True,
            "password": secrets.token_urlsafe(32),   # gesetzt und weggeworfen
            "user_metadata": {"quelle": "scripts/demo_konto.py", "zweck": "Vorfuehrung"},
        })
        if not r.ok:
            sys.exit(f"  ✖ Konto nicht angelegt: {r.status_code} {r.text[:300]}")
        user_id = r.json().get("id")
        print(f"\n  Konto {a.email} angelegt ({str(user_id)[:8]}…) — ohne Mailversand.")
    if not user_id:
        sys.exit("  ✖ Keine Nutzer-Kennung erhalten.")

    # ── 3. Profil setzen ──────────────────────────────────────────────────────
    # `entity_confidence` bleibt bewusst `probable`, NICHT `confirmed`: bestaetigt ist eine
    # Zugehoerigkeit erst ueber Domain oder Adresse (siehe onboarding/page.tsx). Ein
    # Vorfuehr-Konto, das sich selbst als belegt ausgibt, waere dieselbe Sorte Behauptung,
    # gegen die der ganze Onboarding-Beleg gebaut ist.
    profil = {
        "id": user_id, "email": a.email,
        "company_name": f["name"], "identity_id": f["id"],
        "entity_confidence": "probable",
        "confirmed_entities": [f["name"]],
        "cpv_fields": [x["cpv4"] for x in felder],
        "cpv_labels": [x["label"] for x in felder],
        "regions": f.get("regions") or [],
        "branche": "bau",
        "known_from_ted": False,
        "profile": {"firma": f["name"], "identityId": f["id"],
                    "entityConfidence": "unbestaetigt",
                    "confirmedEntities": [{"name": f["name"], "beleg": "selbstauskunft",
                                           "wins": f.get("wins")}],
                    "cpvFields": [x["cpv4"] for x in felder],
                    "cpvLabels": [x["label"] for x in felder],
                    "regions": f.get("regions") or [], "branche": "bau",
                    "quelle": "scripts/demo_konto.py — Vorfuehrung"},
    }
    r = requests.post(f"{url}/rest/v1/user_profiles", headers={
        **kopf, "Prefer": "resolution=merge-duplicates,return=minimal"},
        json=profil, timeout=30)
    if not r.ok:
        sys.exit(f"  ✖ Profil nicht gespeichert: {r.status_code} {r.text[:300]}")
    print(f"  Profil gesetzt: {len(profil['cpv_fields'])} CPV-Felder, "
          f"{len(profil['regions'])} Regionen, branche=bau, Beleglage=probable")

    # ── 4. Anmeldelink — jetzt gefahrlos, das Konto existiert ─────────────────
    # `magiclink` schreibt hier nichts mehr um: die Umschreibung auf `signup` passiert nur
    # bei UNBEKANNTER Adresse, und die haben wir oben ausgeschlossen.
    r = requests.post(f"{url}/auth/v1/admin/generate_link",
                      json={"type": "magiclink", "email": a.email}, headers=kopf, timeout=30)
    if not r.ok:
        sys.exit(f"  ✖ Kein Anmeldelink: {r.status_code} {r.text[:200]}")
    hash_ = ((r.json().get("properties") or r.json())).get("hashed_token")
    if not hash_:
        sys.exit("  ✖ Antwort ohne hashed_token.")

    typ = "magiclink"
    ziel = a.ziel if a.ziel.startswith("/") and not a.ziel.startswith("//") else "/leads"
    print(f"\n  Anmeldelink (eine Stunde gueltig, EINMAL verwendbar):\n")
    print(f"  {a.app}/auth/callback?token_hash={hash_}&type={typ}&next={ziel}\n")
    print("  ⚠ Vor der Vorfuehrung einmal oeffnen ist verbraucht — dann neu erzeugen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

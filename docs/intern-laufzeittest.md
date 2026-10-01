# Laufzeittest des Admin-Portals (/intern) mit Admin-Session

Das Admin-Portal liegt hinter dem Admin-Tor der Middleware (`web/middleware.ts`): nur wessen
E-Mail in `ADMIN_EMAILS` steht (`web/lib/admin.ts`), kommt durch — alle anderen bekommen **404**
(nicht 403: die Existenz der Seite wird nicht verraten). Das gilt **auch lokal**. Ohne
eingeloggte Admin-Session war das Portal deshalb nie durchklickbar; diese Anleitung schließt
die Lücke.

## 1. Admin-Session beschaffen

Zwei Wege:

**A) Dein eigenes Konto.** `sk@skot.de` und `sven.kotzur@gmail.com` stehen in `ADMIN_EMAILS` und
existieren als bestätigte Supabase-Nutzer. Lokal bei `/login` anmelden → `/intern` ist offen.

**B) Wegwerf-Admin (ohne dein Passwort, fuer Automaten/Smoke-Test).**

    python3 scripts/pruefkonto_admin.py        # legt pruef-admin@govisor.invalid an,
                                               # Passwort → .secrets/pruefkonto_admin.txt,
                                               # traegt die Adresse in web/.env.local ADMIN_EMAILS ein
    # danach Dev-Server NEU STARTEN (liest ADMIN_EMAILS beim Start)

Das Konto ist ein `.invalid` (RFC 2606, nie zustellbar), `email_confirm` ohne Mailversand; die
menschlichen Admin-Adressen werden nie angefasst. Danach wieder weg:

    python3 scripts/pruefkonto_admin.py --loeschen   # Konto + ADMIN_EMAILS-Eintrag entfernen
    python3 scripts/pruefkonto_admin.py --status     # nachsehen

⚠ Das Konto liegt in der **Produktions-Supabase** (eigene Instanz `tegznbkbvbbbgzhsvoza`); der
Signup-Trigger legt ihm eine Org + ein Profil an — genau der Mehrfachprofil-Pfad, s. u. Beim
Loeschen bleibt die leere Org zurueck (bei Bedarf per psql entfernen).

## 2. Smoke-Test (automatisch, nur Lesepfade)

    node web/scripts/intern_smoke.mjs            # Basis http://127.0.0.1:3000

Meldet das Wegwerf-Admin-Konto an (echte @supabase/ssr-Cookies, nicht nachgebaut) und prueft:

- **Gate negativ:** ohne Session → `/api/intern/betrieb` = 404.
- **9 APIs mit Session** = 200 + erwartete JSON-Form: betrieb, konten, qualitaet,
  qualitaet+merges, kosten, kuratierung (Index + Datei), zielliste, outreach.
- **7 Seiten** = 200 (Gate offen): /intern, /betrieb, /konten, /qualitaet, /kosten,
  /kuratierung, /vertrieb.

Stand 2026-10-01: **alles gruen** (erster Laufzeitnachweis; vorher nur Datenschicht).

## 3. Manueller Durchklick (was der Automat nicht prueft)

Der Smoke-Test prueft Status + Grobform, nicht Darstellung und nicht die **schreibenden**
Aktionen. Die folgenden von Hand im Browser, als Admin angemeldet:

| Seite | Ansehen | Aktion (⚠ = Seiteneffekt) |
|---|---|---|
| `/intern/betrieb` | Sonden-Ampel, Nachtlauf, Guthaben, Rueckstau | Lauf/Sonde anstossen ⚠ |
| `/intern/konten` | Orgs, Mitglieder, Seats, Plan | Seats/Profile/Plan setzen ⚠; Passwort-Reset-Mail ⚠ |
| `/intern/qualitaet` | Review-Queue, Flags, Dubletten, Merge-Kandidaten | „Kandidaten pruefen" lädt (lesen); `gleich`/`verschieden` schreibt Entscheid ⚠ |
| `/intern/kosten` | Live-Guthaben, Rueckstau, Ausgaben je Modell | — (A-Aktion Modellwahl folgt spaeter) |
| `/intern/kuratierung` | curated-CSVs je Art | Zeile anlegen/loeschen ⚠ (data/-Dateien fail-closed gegen laeuft_was) |
| `/intern/vertrieb` | Zielliste, Trefferquote, Sperre | Landing erzeugen ⚠ (oeffentliche /t/-Seite); Ansprache loggen ⚠ (Sperre) |

⚠ **Mit echten Produktionsdaten vorsichtig testen.** Schreibende Aktionen wirken echt:
- `gleich`/`verschieden` schreibt nach `curated/<L>_entity_merge_entscheidung.csv` und fliesst
  beim naechsten `entity_merge_anwenden`-Lauf + Gold-Rebuild ein (Gold wird durch den Klick
  nie angefasst). Testeintraege hinterher aus der CSV entfernen.
- „Landing erzeugen" legt eine **oeffentliche** `/t/<token>`-Seite fuer eine echte Firma an.
- „Ansprache loggen" setzt eine echte 12-Monats-Sperre (`data/outreach_log.csv`).
- Kuratierungs-Schreiben auf `data/`-Dateien ist fail-closed gegen laufende Laeufe
  (`laeuft_was.sh`) — waehrend des Nachtlaufs/Abrufs gewollt gesperrt (409).

## 4. Mehrfachprofil-Flows (braucht echte Sessions — aus 0024-0027)

1. **Signup + Profil-Wechsel + RLS — ✅ AUTOMATISIERT & GRÜN (2026-10-01):**

       node web/scripts/test_profil_rls.mjs

   Legt zwei Wegwerf-Konten in getrennten Orgs an und prueft gegen den laufenden Dev-Server:
   Signup legt Org+Profil+owner an; A legt ein 2. Profil an (Kontingent vorher auf 2 gehoben)
   und schaltet um (`/api/profil`, `/api/profil/wechseln`); **RLS**: A sieht nur As Profile,
   B nur Bs, B kann As Profil weder lesen noch per API darauf umschalten (404). Raeumt Konten
   **und Orgs** wieder weg (der User-Delete kaskadiert `user_profiles`, aber NICHT die Org —
   das Skript loescht die Org darum selbst; mit `psql` gegengeprueft: 0 Waisen).
2. **Mitglied einladen + Seat-Grenze + Authz — ✅ AUTOMATISIERT & GRÜN (2026-10-01):**

       node web/scripts/test_invite_rls.mjs

   Owner A (seats_paid=2) laedt X ein (POST `/api/org/mitglieder`) → X landet in As **Org**
   (role member, aktives Profil = As Org-Profil), Einladung `eingeloest`, NICHT Solo
   (`handle_new_user`, 0026). Die 3. Person wird abgewiesen (409, belegt = Mitglieder + offene
   Einladungen ≥ seats_paid). Signup OHNE Einladung bekommt eine eigene Solo-Org. Ein Mitglied
   darf nicht einladen (403). Raeumt Konten + Orgs weg (0 Waisen, mit psql gegengeprueft).
   ⚠ Supabase weist `.invalid`-Adressen beim Auth-Invite ab — der Mailversand schlaegt also fehl
   (die Einladung bleibt angelegt), und der Test simuliert den Signup des Eingeladenen; mit einer
   zustellbaren Adresse legt `inviteUserByEmail` den Nutzer schon beim Einladen an. Beide Pfade
   laufen durch dieselbe `handle_new_user`-Zuordnung.
3. **Kauf** (Seats/Profile erweitern) → erwartet **503**, solange Stripe/Preise nicht scharf
   (`lib/stripe.ts`/`lib/preise.ts`); der idempotente Fulfillment-Kern (`kauf_gutschreiben`) steht.
   — noch manuell / offen bis Kostenmodell.

Siehe `docs/mehrfachprofile-migrationsplan.md`.

## 5. Aufraeumen

    python3 scripts/pruefkonto_admin.py --loeschen   # Admin-Testkonto + ADMIN_EMAILS-Eintrag weg
    # danach Dev-Server neu starten

`web/.env.local` und `.secrets/` sind gitignored — die lokale ADMIN_EMAILS-Erweiterung und das
Passwort gelangen nicht ins Repo. In der Produktion steht `ADMIN_EMAILS` in der Deploy-Umgebung;
dieses Werkzeug fasst sie nicht an.

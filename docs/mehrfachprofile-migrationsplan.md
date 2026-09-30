# Mehrfachprofile & Seats — Migrationsplan

Stand 2026-09-30. Konkretisiert [`mehrfachprofile-konzept.md`](mehrfachprofile-konzept.md).
Draft, noch nicht angewandt — das Kostenmodell (Preise/Grenzen) ist offen, das Schema und der
Rollout hier sind davon unabhängig.

## Grundsatz: expand → migrate → contract

Kein Big Bang. Erst **additiv** (neue Tabellen/Spalten, Backfill), dann Code umstellen,
zuletzt **aufräumen** (alte Spalten fallen lassen). Zwischen den Phasen ist das Produkt
jederzeit lauffähig — genau die Vorsicht, die die Auto-Memory einfordert („erst
Determinismus/Lauffähigkeit, dann umbauen").

## Phase 1 — Migration 0024 (additiv, verlustfrei) — GEBAUT 2026-09-30

Umgesetzt in **`supabase/0024_organizations_profiles.sql`** (noch NICHT auf die DB
angewandt). Verbindlich ist die Datei; hier nur die Entscheidungen, damit Doc und SQL nicht
auseinanderlaufen:

- **Tabellen** `organizations` (Name, `plan`, `plan_until`, `seats_paid`, `profiles_paid`) und
  `profiles` (Suchprofil-Felder + `profile`-Blob, `org_id`); `user_profiles` erweitert um
  `org_id`, `active_profile_id`, `role`. RLS im Stil von 0001, `touch_updated_at`-Trigger.
- **Abo/Plan** liegt kuenftig auf der Org (`plan`/`plan_until`); der Backfill kopiert die
  heutigen Werte aus `user_profiles` (0001/0015) in die Org. `user_profiles.plan*` bleibt in
  Phase 1 bestehen (Dual-State), faellt in Phase 3.
- **Backfill** ist ein **idempotenter SQL-DO-Block in der Migration selbst** (nicht ein
  separates Skript): je bestehendem Nutzer eine Org + ein Profil + `role='owner'` +
  `active_profile_id`, `where org_id is null` (erneuter Lauf fasst Migriertes nicht an),
  atomar in einer Transaktion. Direkt danach eine **Selbstpruefung**, die abbricht, wenn ein
  Nutzer ohne Org/aktives Profil bleibt oder ein Profil verwaist ist — ein halber Backfill
  ist damit unmoeglich.

⚠ **Bewusst NICHT in 0024** (sondern Phase 2, mit dem Code zusammen), um ein Schreib-/Lese-
Fenster mit Datenverlust zu vermeiden:
- die `merge_profile`-RPC (0020) auf das aktive Profil umstellen,
- `handle_new_user` (0001) so erweitern, dass Selbst-Registrierung Org+Profil+Owner anlegt
  (und Straggler re-backfillt, die zwischen 0024 und Phase 2 mit `org_id=null` entstehen),
- die Trigger, die `seats_paid`/`profiles_paid` durchsetzen.

**Verifikation**: gegen ein lokales Postgres 17 (Wegwerf-Cluster, Supabase-Teile gestubbt)
gelaufen — Backfill korrekt (Feld-/Plan-Kopie, Fallback-Name), Selbstpruefung greift,
**idempotent** (zweiter Lauf doppelt nichts). Belegt sind damit DDL, Backfill und Idempotenz.
⚠ NICHT belegt (weil `auth.uid()` nur ein Stub war): die **RLS-Laufzeit** (sieht ein Mitglied
wirklich nur die Profile seiner Org?) und der Signup-Trigger aus Phase 2. Vor dem Anwenden auf
die Produktion gehoert deshalb weiterhin ein Lauf gegen eine **Dev-Instanz** — das ist Svens
Startschuss, nicht meiner. Angewandt ist die Migration NICHT.

## Phase 2 — Code umstellen (aktives Profil) — VORBEREITET 2026-09-30

**DB-Seite** in `supabase/0025_active_profile_switch.sql`, lokal gegen PG17 verifiziert:
`merge_profile` schreibt ins aktive Profil (sonst `user_profiles`); `handle_new_user` legt bei
Selbst-Registrierung Org+Profil+Owner an (Invite-Nutzer ausgenommen); Straggler-Nachzug;
Grenzen-Trigger fuer `profiles_paid`/`seats_paid`. Belegt: RPC trifft aktives Profil, Signup
legt an, 2. Profil/Nutzer wird abgewiesen, mit erhoehtem Kontingent zugelassen.

**Code-Seite** gebaut und tsc-sauber, **tolerant** (ohne aktives Profil exakt wie heute, darf
also vor dem Anwenden in `main` liegen): `auth.ts` `aktivesProfilId` + `loadProfile`/
`saveProfile` (Blob + Such-Spalten ins aktive Profil, Konto-Spalten am Nutzer), `account.ts`
`loadAccount` ueberlagert /settings mit dem aktiven Profil, neue Route
`/api/profil/wechseln`, Client-Helfer `wechsleProfil` in `useProfil.ts`.

⚠ **Phase 2b (offen)**: Profil-Umschalter-UI und Profil-Verwaltung (anlegen/umbenennen/
loeschen), Invite-Flow fuer weitere Seats, Kauf von Seats/Profilen — Letzteres haengt am
Kostenmodell. Und: RLS-Laufzeit + der ganze Umschalt-Kreis brauchen einen Lauf gegen eine
Supabase-Instanz mit angewandten 0024/0025 (hier nicht moeglich).

Umbaupunkte (umgesetzt):

| Datei / Stelle | heute | nachher |
|---|---|---|
| `lib/supabase/auth.ts` `loadProfile` | `select profile … where id = user.id` | Profil des `active_profile_id` laden |
| `lib/supabase/auth.ts` `saveProfile` | `update user_profiles …` (Spalten+Blob) | in `profiles` des aktiven Profils schreiben |
| `lib/supabase/profilBlob.ts` `mischeProfilBlob` + RPC `merge_profile` | schreibt `user_profiles.profile` von `auth.uid()` | schreibt `profiles.profile` des aktiven Profils (RPC entsprechend anpassen, `security definer` mit Org-Check) |
| `lib/useProfil.ts` | lädt das eine Profil | lädt aktives Profil + stellt Umschalter bereit |
| Engine (`explorerCore.js`, `profileEngine.js`) | liest `userProfile` | unverändert — bekommt weiterhin EIN `userProfile`, nur ist es das aktive |
| APIs, die `user_profiles` lesen (`blocks`, `alerts`, `netz`, `firma`, `account/delete`, `intern/claims`) | je nach Zweck | Konto-bezogen bleibt an `user_profiles`; **profil-bezogen** (Suchprofil, Relevanz) auf `active_profile_id` |

Neu: eine Route zum **Profil wechseln** (`active_profile_id` setzen) und zum **Profile/Seats
verwalten** (anlegen/umbenennen/löschen, Mitglieder einladen — Letzteres mit dem Invite-Flow).

## Phase 3 — Aufräumen (contract)

Wenn nichts mehr die alten Suchprofil-Spalten in `user_profiles` liest: sie in einer späteren
Migration entfernen (`cpv_fields`, `regions`, `vol_*`, `profile` …). `user_profiles` behält
Auth/Rolle/`org_id`/`active_profile_id`.

## Grenzen durchsetzen (Seats & Profile)

- **Profil anlegen**: prüfen `count(profiles where org_id=…) < organizations.profiles_paid`.
- **Nutzer einladen**: prüfen `count(user_profiles where org_id=…) < organizations.seats_paid`.
- Am besten als DB-Trigger (fail-closed) **und** in der App (freundliche Meldung).

## Offen (Kostenmodell, Svens Entscheidung)

- Preis je Seat und je Profil; Frei-Grenzen im `free`-Plan (`seats_paid`/`profiles_paid`-Defaults).
- Billing pro Profil oder pro Org.
- Erst wenn diese Beträge feststehen, lohnt der Bau von Phase 1; das Schema oben ändert sich
  dadurch nicht, nur die Default-Grenzen.

## Absicherung

- Backfill-Skript idempotent, mit Vorher/Nachher-Zählung und 0-Waisen-Prüfung (FK).
- Ein `pruefe_*`-Test: nach der Migration hat jeder Nutzer genau eine Org, genau ein aktives
  Profil, und kein `profiles.org_id` ist verwaist.
- Phasen einzeln deploybar; zwischen den Phasen läuft das Produkt.

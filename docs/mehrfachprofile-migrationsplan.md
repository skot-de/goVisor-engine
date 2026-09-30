# Mehrfachprofile & Seats — Migrationsplan

Stand 2026-09-30. Konkretisiert [`mehrfachprofile-konzept.md`](mehrfachprofile-konzept.md).
Draft, noch nicht angewandt — das Kostenmodell (Preise/Grenzen) ist offen, das Schema und der
Rollout hier sind davon unabhängig.

## Grundsatz: expand → migrate → contract

Kein Big Bang. Erst **additiv** (neue Tabellen/Spalten, Backfill), dann Code umstellen,
zuletzt **aufräumen** (alte Spalten fallen lassen). Zwischen den Phasen ist das Produkt
jederzeit lauffähig — genau die Vorsicht, die die Auto-Memory einfordert („erst
Determinismus/Lauffähigkeit, dann umbauen").

## Phase 1 — Migration 0011 (additiv, verlustfrei)

Nächste freie Nummer: `supabase/0011_organizations_profiles.sql`. Skizze:

```sql
-- Organisationen: das Unternehmen (z. B. Canom). Traeger von Seats und Profilen.
create table if not exists public.organizations (
  id            uuid primary key default gen_random_uuid(),
  name          text not null,
  plan          text not null default 'free' check (plan in ('free','paid','cancelled')),
  seats_paid    int  not null default 1,   -- erlaubte Nutzer
  profiles_paid int  not null default 1,   -- erlaubte Profile
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

-- Suchprofile: gehoeren der Org, nicht dem Nutzer. Die Felder wandern konzeptionell aus
-- user_profiles hierher (in Phase 3 dort entfernt).
create table if not exists public.profiles (
  id                 uuid primary key default gen_random_uuid(),
  org_id             uuid not null references public.organizations(id) on delete cascade,
  name               text not null default 'Standard',
  identity_id        text,
  confirmed_entities text[] not null default '{}',
  cpv_fields         text[] not null default '{}',
  cpv_labels         text[] not null default '{}',
  regions            text[] not null default '{}',
  region_labels      text[] not null default '{}',
  vol_min            numeric,
  vol_max            numeric,
  branche            text,
  profile_type       text not null default 'bidder'
                     check (profile_type in ('bidder','contracting_authority')),
  profile            jsonb,                -- der Engine-Blob, wie heute
  created_by         uuid references public.user_profiles(id) on delete set null,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);

-- user_profiles bleibt Auth-Spiegel, bekommt Mitgliedschaft + aktives Profil.
alter table public.user_profiles
  add column if not exists org_id            uuid references public.organizations(id) on delete cascade,
  add column if not exists active_profile_id uuid references public.profiles(id)      on delete set null,
  add column if not exists role              text not null default 'owner'
                                             check (role in ('owner','admin','member'));
```

RLS (Stil wie 0001):

```sql
alter table public.organizations enable row level security;
alter table public.profiles      enable row level security;

-- Mitglieder sehen ihre Org; nur owner/admin aendern sie.
create policy "org_select_member" on public.organizations for select
  using (id = (select org_id from public.user_profiles where id = auth.uid()));
create policy "org_update_admin"  on public.organizations for update
  using (id = (select org_id from public.user_profiles where id = auth.uid())
         and (select role from public.user_profiles where id = auth.uid()) in ('owner','admin'));

-- Mitglieder sehen/nutzen die Profile ihrer Org; owner/admin legen an/aendern.
create policy "profiles_select_member" on public.profiles for select
  using (org_id = (select org_id from public.user_profiles where id = auth.uid()));
create policy "profiles_write_admin"   on public.profiles for all
  using (org_id = (select org_id from public.user_profiles where id = auth.uid())
         and (select role from public.user_profiles where id = auth.uid()) in ('owner','admin'))
  with check (org_id = (select org_id from public.user_profiles where id = auth.uid()));
```

Backfill (jedes heutige 1:1-Profil → Org + Profil + Owner):

```sql
-- 1) je Nutzer eine Org
insert into public.organizations (id, name, plan)
  select gen_random_uuid(), coalesce(nullif(trim(company_name),''), 'Mein Unternehmen'), plan
  from public.user_profiles where org_id is null;
-- (Zuordnung Org↔Nutzer ueber eine temporaere Hilfsspalte oder ein Skript, 1:1)
-- 2) je Nutzer ein Profil mit den bisherigen Feldern (inkl. profile-Blob)
-- 3) user_profiles.org_id, .active_profile_id setzen, role='owner'
```

⚠ Der Backfill ist der heikelste Teil (die 1:1-Zuordnung Org↔Profil↔Nutzer). Er gehört in
ein **idempotentes Skript** (`scripts/migrate_0011_profiles.py`) mit Vorher/Nachher-Zählung,
nicht in reines SQL — dieselbe Sorgfalt wie bei `normalize_notice_ids.py`.

Trigger `handle_new_user` (0001) wird erweitert: **Selbst-Registrierung** legt Org + erstes
Profil + `role='owner'` + `active_profile_id` an. **Eingeladene** Nutzer (Invite-Flow, später)
bekommen `org_id`/`role` von der App gesetzt und legen KEINE neue Org an.

## Phase 2 — Code umstellen (aktives Profil)

Additiv bereits lauffähig (jede Org hat genau ein Profil = wie heute). Jetzt die Lesewege auf
`active_profile_id` umstellen:

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

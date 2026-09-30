# Mehrfachprofile & Seats — Konzept

Stand 2026-09-30. Entscheidung von Sven; Kostenmodell noch in Arbeit, das Schema hier ist
davon unabhängig baubar.

## Ausgangslage (heute)

Strikt 1:1. `public.user_profiles.id = auth.users.id` — ein Login trägt genau **ein**
Suchprofil (`cpv_fields`, `cpv_labels`, `regions`, `vol_min/max`, `identity_id`,
`confirmed_entities`, dazu der `profile`-jsonb-Blob). Die Relevanz-Engine liest dieses eine
`userProfile` (Ladeweg: `web/lib/supabase/auth.ts`, `profilBlob.ts`). Ein Unternehmen mit
mehreren Sparten/Regionen/Töchtern kann heute nicht mehrere Profile führen.

## Ziel

- Ein **Unternehmen** kann **mehrere Profile** führen.
- **Seats** (Nutzer je Unternehmen) und **Profile** sind kaufbar — zwei getrennte Kauf-Achsen.
- Ein **User nutzt genau ein Profil aktiv**. Er darf zwischen den Profilen seiner Org
  wechseln, aber immer nur eines gleichzeitig aktiv.

## Datenmodell

| Tabelle | Zweck | Kernfelder |
|---|---|---|
| `organizations` | das Unternehmen (z. B. Canom) | `id, name, plan, seats_paid, profiles_paid, billing_*, created_at` |
| `profiles` | die Suchprofile, **der Org gehörend** | `id, org_id → organizations, name, cpv_fields, cpv_labels, regions, region_labels, vol_min, vol_max, identity_id, confirmed_entities, profile (jsonb), created_by, created_at` |
| `user_profiles` (erweitert) | Auth-Spiegel **+ Mitgliedschaft** | heutige Auth-/Plan-Spalten `+ org_id → organizations, + active_profile_id → profiles, + role ('owner'|'admin'|'member')` |

Die heutigen Suchprofil-Spalten wandern konzeptionell von `user_profiles` nach `profiles`;
`user_profiles` behält Auth/Rolle/aktives Profil.

## Regeln

- **Ein aktives Profil je User**: `user_profiles.active_profile_id`. Wechseln = dieses Feld
  umsetzen. Die Engine liest ab jetzt das **aktive** Profil statt „das eine".
- **Zwei Kauf-Achsen**: `seats_paid` (erlaubte User je Org) und `profiles_paid` (erlaubte
  `profiles`-Zeilen je Org). Beim Anlegen eines Users bzw. Profils gegen die Grenze prüfen.
- **Sichtbarkeit**: ein Mitglied darf die Profile **seiner** Org sehen und (sofern erlaubt)
  aktiv setzen. Feinere Pro-Profil-Zugriffsrechte sind später ergänzbar, ohne das Schema zu
  brechen.

## RLS

- `organizations`: lesbar für Mitglieder der Org (`user_profiles.org_id = organizations.id`).
- `profiles`: lesbar/wählbar für Mitglieder der zugehörigen Org; schreibbar für `owner`/`admin`.
- `user_profiles`: eigene Zeile wie heute; Org-Owner/Admin dürfen Mitglieder ihrer Org sehen
  (für Seats-Verwaltung im Admin-Center bzw. Org-Self-Service).

## Migrationspfad (verlustfrei)

Jedes heutige `user_profiles` wird zu:
1. einer `organizations`-Zeile (Name aus `company_name`),
2. einem `profiles`-Eintrag mit den bisherigen Suchprofil-Feldern,
3. dem User als `owner`, dessen `active_profile_id` auf dieses eine Profil zeigt.

Keine Suchprofil-Daten gehen verloren; Ein-Personen-Konten sehen nach der Migration genau
wie vorher aus (eine Org, ein Profil).

## Was sich im Code ändert

- **Profil-Ladeweg** (`auth.ts`, `profilBlob.ts`): brauchen eine `profile_id` (das aktive),
  nicht mehr die User-id als Profilschlüssel.
- **Jede `userProfile`-Lesestelle** (Relevanz-Engine, `/api/leads`, `lead-detail`, Strategie,
  Radius/Region) bezieht das aktive Profil.
- **Billing-Gate** (`entity_confidence`, Plan): entscheidet sich pro Org bzw. pro Profil —
  offen, hängt am Kostenmodell.
- **Profil-Umschalter** im Frontend.

## Offen (Kostenmodell, Svens Entscheidung)

- Preis je Seat und je Profil, Frei-Grenzen im `free`/`paid`-Plan.
- Billing pro Profil oder pro Konto/Org.

Das Schema oben ist von diesen Beträgen unabhängig und kann vorab gebaut werden.

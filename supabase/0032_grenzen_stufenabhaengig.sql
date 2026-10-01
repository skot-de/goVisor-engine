-- Profil- und Sitzgrenze stufenabhaengig: nur Free und Testphase sind begrenzt.
--
-- Preismodell v1.9 §7.3: „Auf Analyse und Strategie gibt es keine Obergrenze." Die drei
-- Trigger setzten `profiles_paid` bzw. `seats_paid` aber UNBEDINGT durch, ohne die Stufe
-- anzusehen (live gelesen am 2026-10-01: `tier` kam in keiner der drei Funktionen vor).
--
-- ⚠ WARUM DAS BISHER NICHT AUFFIEL, und warum es beim ERSTEN bezahlten Abschluss gekippt
-- waere. Alle 13 Organisationen stehen auf `tier='free'` mit `profiles_paid=1` und genau
-- einem Profil. Free ist laut §7.3 auf eins begrenzt — der Trigger tat also versehentlich
-- das Richtige. Sobald eine Organisation auf `analyse` geht, verweigert die Datenbank das
-- zweite Profil und den zweiten Nutzer, obwohl das Preismodell beides als unbegrenzt
-- verkauft und die Erweiterung zu 29 € genau dafuer da ist. Der Kunde zahlt, und der
-- Trigger sagt „Kontingent erreicht".
--
-- ⚠ WAS DADURCH MOEGLICH WIRD UND GEWOLLT IST: `count(profiles) > profiles_paid`. Genau
-- dieser Zustand TRAEGT die Proration (§13: „Proration bei jeder Erweiterungsaenderung
-- unterjaehrig"). Der Kunde legt ein Profil an, die Menge steigt, die Rechnung folgt. Der
-- Trigger darf das nicht verhindern, sonst gibt es keine Erweiterung, die man freigeben
-- koennte. **`profiles_paid`/`seats_paid` sind ab hier ABRECHNUNGSGROESSEN und keine
-- Erlaubnis mehr.** Die Kommentare in 0024 („erlaubte Profile") werden mit nachgezogen.
--
-- ⚠ FAIL-CLOSED IN DER POSITIVEN FORM. Geprueft wird `tier in ('analyse','strategie')` und
-- nicht `tier not in ('free','trial')`. Grund: faende die Abfrage keine Organisation, waere
-- `t` NULL, und `NULL not in (…)` ist NULL — der Riegel waere uebersprungen. In der
-- positiven Form ist NULL ebenfalls nicht wahr und die Grenze greift. Jede unbekannte Stufe
-- ist damit begrenzt, nicht frei.
--
-- Die Grenze fuer Free/Testphase ist fest 1 (§7.3: „genau 1"), NICHT `profiles_paid`. Das
-- ist eine Stufengrenze, keine Abrechnungsgrenze: ein Free-Konto rechnet nichts ab, also
-- darf eine Abrechnungsmenge dort auch nichts erlauben.
-- Idempotent.

create or replace function public.pruefe_profil_grenze()
returns trigger language plpgsql as $$
declare n int; t text;
begin
  select tier into t from public.organizations where id = new.org_id;
  if t in ('analyse', 'strategie') then
    return new;                      -- bezahlt: keine Obergrenze (§7.3)
  end if;
  select count(*) into n from public.profiles where org_id = new.org_id;
  if n >= 1 then
    raise exception 'Free und Testphase fuehren genau ein Unternehmensprofil (Stufe: %).',
      coalesce(t, 'unbekannt') using errcode = 'check_violation';
  end if;
  return new;
end;
$$;

create or replace function public.pruefe_seat_grenze()
returns trigger language plpgsql as $$
declare n int; t text;
begin
  select tier into t from public.organizations where id = new.org_id;
  if t in ('analyse', 'strategie') then
    return new;
  end if;
  select count(*) into n from public.user_profiles where org_id = new.org_id;
  if n >= 1 then
    raise exception 'Free und Testphase fuehren genau einen Nutzer (Stufe: %).',
      coalesce(t, 'unbekannt') using errcode = 'check_violation';
  end if;
  return new;
end;
$$;

create or replace function public.pruefe_invite_seat()
returns trigger language plpgsql as $$
declare belegt int; t text;
begin
  select tier into t from public.organizations where id = new.org_id;
  if t in ('analyse', 'strategie') then
    return new;
  end if;
  -- Auf Free/Testphase ist der eine Sitz der Inhaber selbst, es bleibt also keiner zum
  -- Einladen uebrig. Gezaehlt wird trotzdem beides (Mitglieder + offene Einladungen),
  -- damit die Meldung stimmt, wenn der Inhaber noch fehlt.
  select (select count(*) from public.user_profiles where org_id = new.org_id)
       + (select count(*) from public.pending_invites
            where org_id = new.org_id and status = 'offen')
    into belegt;
  if belegt >= 1 then
    raise exception 'Free und Testphase fuehren genau einen Nutzer, Einladungen brauchen '
                    'Analyse oder Strategie (Stufe: %).',
      coalesce(t, 'unbekannt') using errcode = 'check_violation';
  end if;
  return new;
end;
$$;

comment on column public.organizations.profiles_paid is
  'ABGERECHNETE Unternehmensprofile, nicht erlaubte. Seit 0032 begrenzt sie nichts mehr: '
  'count(profiles) > profiles_paid ist erlaubt und traegt die Proration (§5.2/§13).';
comment on column public.organizations.seats_paid is
  'ABGERECHNETE Nutzer, nicht erlaubte. Siehe profiles_paid.';

-- Mehrfachprofile & Seats — Phase 2b: Kauf/Entitlement. Baut auf 0024–0026 auf.
--
-- Erhoeht organizations.seats_paid / profiles_paid gegen Bezahlung — GENAU EINMAL je
-- Zahlungsereignis. Der Kauf-Flow (Stripe) haengt am offenen Kostenmodell; dieser
-- geld-sichere Kern (Idempotenz gegen Webhook-Retries) steht und ist unabhaengig davon.

create table if not exists public.purchases (
  id            uuid primary key default gen_random_uuid(),
  org_id        uuid not null references public.organizations(id) on delete cascade,
  art           text not null check (art in ('seat','profile')),
  menge         int  not null check (menge > 0),
  betrag_cents  int,
  waehrung      text not null default 'eur',
  provider      text not null default 'stripe',
  provider_ref  text not null,                       -- z.B. Stripe checkout.session.id
  status        text not null default 'erfuellt' check (status in ('erfuellt','storniert')),
  created_at    timestamptz not null default now(),
  unique (provider, provider_ref)                    -- Idempotenz: ein Ereignis nur einmal
);
create index if not exists purchases_org_idx on public.purchases (org_id);

alter table public.purchases enable row level security;
-- Mitglieder sehen die Kaeufe ihrer Org (Rechnungshistorie). Geschrieben wird NUR serverseitig
-- ueber kauf_gutschreiben (security definer) — kein Insert-Policy fuer Clients.
drop policy if exists "purchases_select_member" on public.purchases;
create policy "purchases_select_member" on public.purchases for select
  using (org_id = (select org_id from public.user_profiles where id = auth.uid()));

-- Idempotente Gutschrift: verbucht den Kauf und erhoeht das Kontingent GENAU EINMAL je
-- (provider, provider_ref). Ein zweiter Aufruf mit derselben Referenz (Webhook-Retry) ist ein
-- No-op. Rueckgabe: 'gutgeschrieben' | 'schon_verbucht'.
create or replace function public.kauf_gutschreiben(
  p_org uuid, p_art text, p_menge int, p_provider text, p_ref text,
  p_cents int default null, p_waehrung text default 'eur'
) returns text language plpgsql security definer set search_path = public as $$
declare v_count int;
begin
  if p_art not in ('seat','profile') then raise exception 'ungueltige art: %', p_art; end if;
  if p_menge is null or p_menge <= 0 then raise exception 'menge muss > 0 sein'; end if;
  insert into public.purchases (org_id, art, menge, betrag_cents, waehrung, provider, provider_ref)
    values (p_org, p_art, p_menge, p_cents, p_waehrung, p_provider, p_ref)
    on conflict (provider, provider_ref) do nothing;
  get diagnostics v_count = row_count;
  if v_count = 0 then return 'schon_verbucht'; end if;   -- Retry → nichts erhoehen
  if p_art = 'seat' then
    update public.organizations set seats_paid    = seats_paid    + p_menge where id = p_org;
  else
    update public.organizations set profiles_paid = profiles_paid + p_menge where id = p_org;
  end if;
  return 'gutgeschrieben';
end;
$$;
revoke all on function public.kauf_gutschreiben(uuid,text,int,text,text,int,text) from public;

-- Bausteine: persönlich, mit ausdrücklicher Freigabe an die Firma (Ticket #23 §9).
--
-- AUSGANGSLAGE. 0006 legte `profile_text_blocks` mit einer einzigen Regel an:
-- `auth.uid() = profile_id` für alles. Damit ist jeder Baustein privat, und die Oberfläche
-- versprach etwas anderes („gehören dem Unternehmen, nicht der einzelnen Person").
--
-- ENTSCHEIDUNG. Nicht die Oberfläche hat recht und nicht das Schema, sondern beides zur
-- Hälfte: ein Baustein gehört der Person, die ihn angelegt hat, und SIE entscheidet, ob die
-- Firma ihn sieht. Wer die Firma wechselt, nimmt seine privaten Bausteine mit; die
-- freigegebenen bleiben, wo sie freigegeben wurden, bis der Eigentümer sie zurückzieht.
--
-- ⚠ WARUM DIE FREIGABE NICHT AN `user_profiles.identity_id` HÄNGT.
-- Dieses Feld ist eine SELBSTAUSKUNFT: `saveIdentityCorrection` lässt jeden Nutzer es frei
-- setzen (§7.3, Identitäts-Korrektur), und die RLS erlaubt das Ändern der eigenen Zeile.
-- Eine Firmenfreigabe, die nur darauf schaut, wäre eine offene Tür: wer den Namen einer
-- fremden Firma einträgt, läse deren Bausteine. Massgeblich ist deshalb der BELEGTE
-- Anspruch in `identity_claims` (Status `belegt` oder `geprueft`) — den vergibt
-- `/api/entity-verify` über die Firmen-Domain, nicht der Nutzer über ein Textfeld.

alter table public.profile_text_blocks
  add column if not exists sichtbarkeit text not null default 'privat',
  add column if not exists identity_id text;

do $$ begin
  alter table public.profile_text_blocks
    add constraint ptb_sichtbarkeit_check check (sichtbarkeit in ('privat','firma'));
exception when duplicate_object then null; end $$;

-- Ein freigegebener Baustein OHNE Firma waere fuer niemanden sichtbar und saehe trotzdem
-- freigegeben aus. Solche Zustaende gar nicht erst zulassen.
do $$ begin
  alter table public.profile_text_blocks
    add constraint ptb_firma_braucht_identity
    check (sichtbarkeit <> 'firma' or identity_id is not null);
exception when duplicate_object then null; end $$;

create index if not exists ptb_firma_idx on public.profile_text_blocks (identity_id)
  where sichtbarkeit = 'firma' and archived = false;

-- ── Regeln: lesen weiter als schreiben ───────────────────────────────────────────────────
-- Die alte Regel galt FOR ALL. Getrennt, weil Kolleginnen einen freigegebenen Baustein
-- LESEN, aber nicht aendern oder archivieren duerfen — sonst nimmt jemand anderes einem
-- Menschen seinen Text weg.
drop policy if exists "ptb_rw_own" on public.profile_text_blocks;

drop policy if exists "ptb_select" on public.profile_text_blocks;
create policy "ptb_select" on public.profile_text_blocks for select using (
  auth.uid() = profile_id
  or (sichtbarkeit = 'firma' and identity_id is not null and exists (
        select 1 from public.identity_claims c
        where c.user_id = auth.uid()
          and c.identity_id = profile_text_blocks.identity_id
          and c.status in ('belegt','geprueft')))
);

drop policy if exists "ptb_insert" on public.profile_text_blocks;
create policy "ptb_insert" on public.profile_text_blocks for insert with check (
  auth.uid() = profile_id
  and (sichtbarkeit = 'privat' or exists (
        select 1 from public.identity_claims c
        where c.user_id = auth.uid()
          and c.identity_id = profile_text_blocks.identity_id
          and c.status in ('belegt','geprueft')))
);

drop policy if exists "ptb_update" on public.profile_text_blocks;
create policy "ptb_update" on public.profile_text_blocks for update
  using (auth.uid() = profile_id)
  with check (
    auth.uid() = profile_id
    and (sichtbarkeit = 'privat' or exists (
          select 1 from public.identity_claims c
          where c.user_id = auth.uid()
            and c.identity_id = profile_text_blocks.identity_id
            and c.status in ('belegt','geprueft')))
  );

drop policy if exists "ptb_delete" on public.profile_text_blocks;
create policy "ptb_delete" on public.profile_text_blocks for delete using (auth.uid() = profile_id);

comment on column public.profile_text_blocks.sichtbarkeit is
  'privat = nur die anlegende Person; firma = alle mit belegtem Anspruch auf identity_id';
comment on column public.profile_text_blocks.identity_id is
  'Firma, in die freigegeben wurde. Beim Freigeben gesetzt, nicht mitwandernd.';

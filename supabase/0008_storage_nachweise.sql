-- #27 §8 / §23 §12.3 — Nachweis-Uploads (Zertifikate) im privaten Storage-Bucket.
-- Profilgebunden, nie in geteilten Ebenen: RLS über den user-id-Pfadpräfix. Verschlüsselung
-- at-rest liefert Supabase Storage serverseitig. Idempotent.
-- Anwenden: psql "$CONN" -f supabase/0008_storage_nachweise.sql

-- Privater Bucket (nicht öffentlich lesbar; nur via signierte URLs / RLS).
insert into storage.buckets (id, name, public)
values ('nachweise', 'nachweise', false)
on conflict (id) do nothing;

-- RLS auf storage.objects: jeder Nutzer sieht/schreibt nur unter seinem eigenen Ordner
-- <auth.uid()>/…  (foldername[1] = user-id). Keine geteilte Ebene.
do $$
begin
  if not exists (select 1 from pg_policies where schemaname='storage' and tablename='objects' and policyname='nachweise_read_own') then
    create policy nachweise_read_own on storage.objects for select to authenticated
      using (bucket_id = 'nachweise' and (storage.foldername(name))[1] = auth.uid()::text);
  end if;
  if not exists (select 1 from pg_policies where schemaname='storage' and tablename='objects' and policyname='nachweise_insert_own') then
    create policy nachweise_insert_own on storage.objects for insert to authenticated
      with check (bucket_id = 'nachweise' and (storage.foldername(name))[1] = auth.uid()::text);
  end if;
  if not exists (select 1 from pg_policies where schemaname='storage' and tablename='objects' and policyname='nachweise_update_own') then
    create policy nachweise_update_own on storage.objects for update to authenticated
      using (bucket_id = 'nachweise' and (storage.foldername(name))[1] = auth.uid()::text);
  end if;
  if not exists (select 1 from pg_policies where schemaname='storage' and tablename='objects' and policyname='nachweise_delete_own') then
    create policy nachweise_delete_own on storage.objects for delete to authenticated
      using (bucket_id = 'nachweise' and (storage.foldername(name))[1] = auth.uid()::text);
  end if;
end $$;

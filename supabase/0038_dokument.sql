-- 0038 — Dokumente aus Bausteinen: zusammenstellen, spaeter exportieren.
--
-- WOZU. Die Wettbewerbsanalyse vom 4./5. Oktober kommt zu einem unbequemen Ergebnis: wir haben
-- mehrere Alleinstellungen, aber praktisch keinen Burggraben — die kuerzesten Vorspruenge sind
-- Wochen. Der einzige echte Wechselkosten-Graben sind die DATEN DES KUNDEN. Sobald Referenzen,
-- Zertifikate und zusammengestellte Dokumente einer Firma bei uns liegen, kostet ein Wechsel sie
-- etwas. Die Bausteinbibliothek ist der Anfang; diese Tabellen machen sie nuetzlich genug, dass
-- jemand sie wirklich fuellt. Plan: `docs/funktion-dokument-bauen.md`.
--
-- ⚠ VERWEIS, NICHT KOPIE — die wichtigste Entscheidung in diesem Schema. Ein Teil zeigt entweder
-- AUF einen Baustein oder traegt eigenen Text. Eine Kopie veraltet still: wer seine
-- ISO-Zertifikatsnummer in der Bibliothek pflegt, haette sie in zwoelf alten Dokumenten
-- weiterhin falsch stehen, ohne es zu merken. Wer eine Fassung einfrieren WILL, wandelt den Teil
-- ausdruecklich in freien Text um — ein Knopf, kein Automatismus.
--
-- ⚠ HIER GILT „WIR SPEICHERN NICHTS" NICHT. Dieser Satz stammt aus 0037 (Fragebogen) und darf
-- nicht uebernommen werden: ein Dokument wird ABSICHTLICH gespeichert, das ist sein Zweck. Also
-- verschluesselt wie die Bausteine, loeschbar, und in der Oberflaeche als gespeichert erkennbar.

create table if not exists public.profile_dokument (
  id            uuid primary key default gen_random_uuid(),
  org_id        uuid        not null,
  -- ⚠ Dieselbe Verwechslungsgefahr wie in 0037: `user_profiles.id` IST die Auth-Kennung (0001),
  --   und `profile_text_blocks.profile_id` zeigt genau darauf — Bausteine haengen am NUTZER.
  --   Die Mehrfachprofile aus `profiles` (0033) sind etwas anderes und haben damit nichts zu tun.
  profil_id     uuid        not null references public.user_profiles (id) on delete cascade,
  titel         text        not null default 'Ohne Titel',
  -- Der Vorgang, zu dem das Dokument gehoert. Nullable: eine Vorlage gehoert zu keinem.
  lead_id       text,
  erstellt_at   timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create table if not exists public.profile_dokument_teil (
  id            uuid primary key default gen_random_uuid(),
  dokument_id   uuid        not null references public.profile_dokument (id) on delete cascade,
  -- Luecken sind erlaubt und erwuenscht: Umsortieren schreibt neue Positionen, ohne dass alle
  -- Zeilen angefasst werden muessen. Deshalb KEIN unique auf (dokument_id, position) — zwei
  -- Teile duerfen waehrend eines Umbaus kurz dieselbe Position tragen.
  position      integer     not null,
  art           text        not null check (art in ('baustein', 'ueberschrift', 'text')),
  -- Gesetzt genau dann, wenn art = 'baustein'. `on delete set null` und NICHT cascade: wer einen
  -- Baustein loescht, soll nicht stillschweigend Absaetze aus fertigen Dokumenten verlieren —
  -- der Teil bleibt stehen und die Oberflaeche zeigt, dass seine Quelle weg ist.
  baustein_id   uuid        references public.profile_text_blocks (id) on delete set null,
  -- Gesetzt bei 'ueberschrift' und 'text'. Umschlagverfahren wie `profile_text_blocks` (§12.3):
  -- es waere absurd, Bausteine zu verschluesseln und den daraus gebauten Text eine Tabelle
  -- weiter offen liegen zu lassen.
  inhalt_encrypted bytea,
  -- Nur fuer 'ueberschrift': 1 bis 3.
  ebene         smallint    check (ebene is null or ebene between 1 and 3),
  updated_at    timestamptz not null default now(),

  -- Die Form haengt an der Art, und zwar hart. Ohne diese Bedingung entstehen Teile, die weder
  -- einen Baustein noch Text tragen — sie sehen in der Liste aus wie ein Absatz und sind leer.
  constraint teil_form check (
    (art = 'baustein'     and baustein_id is not null and inhalt_encrypted is null)
    or (art in ('ueberschrift', 'text') and baustein_id is null and inhalt_encrypted is not null)
  )
);

create index if not exists profile_dokument_profil_idx
  on public.profile_dokument (profil_id, updated_at desc);
create index if not exists profile_dokument_lead_idx
  on public.profile_dokument (lead_id) where lead_id is not null;
create index if not exists profile_dokument_teil_idx
  on public.profile_dokument_teil (dokument_id, position);

comment on table public.profile_dokument is
  'Aus Bausteinen zusammengestelltes Dokument (Plan: docs/funktion-dokument-bauen.md). '
  'Teile verweisen auf Bausteine statt sie zu kopieren, damit gepflegte Bausteine nicht in '
  'alten Dokumenten veralten.';

comment on column public.profile_dokument_teil.baustein_id is
  'on delete set null, NICHT cascade: ein geloeschter Baustein darf keinen Absatz aus einem '
  'fertigen Dokument entfernen. Der Teil bleibt, die Oberflaeche zeigt die fehlende Quelle.';

-- ── Zugriff ─────────────────────────────────────────────────────────────────────────────────
-- Form aus 0027, die nachweislich laeuft: `user_profiles.id` IST die Auth-Kennung, es gibt dort
-- KEIN `user_id`. In 0037 stand zuerst `p.user_id = auth.uid()` — die Migration waere beim
-- Anwenden an einer nicht existierenden Spalte gescheitert.
alter table public.profile_dokument      enable row level security;
alter table public.profile_dokument_teil enable row level security;

drop policy if exists dokument_lesen on public.profile_dokument;
create policy dokument_lesen on public.profile_dokument
  for select to authenticated
  using (org_id = (select org_id from public.user_profiles where id = auth.uid()));

drop policy if exists dokument_anlegen on public.profile_dokument;
create policy dokument_anlegen on public.profile_dokument
  for insert to authenticated
  with check (org_id = (select org_id from public.user_profiles where id = auth.uid())
              and profil_id = auth.uid());

-- ⚠ Aendern und Loeschen nur am EIGENEN Dokument, nicht an allen der Organisation. Lesen darf
--   die ganze Firma (ein Angebot entsteht gemeinsam), aber wer es umbaut, soll es besitzen.
drop policy if exists dokument_aendern on public.profile_dokument;
create policy dokument_aendern on public.profile_dokument
  for update to authenticated using (profil_id = auth.uid()) with check (profil_id = auth.uid());

drop policy if exists dokument_loeschen on public.profile_dokument;
create policy dokument_loeschen on public.profile_dokument
  for delete to authenticated using (profil_id = auth.uid());

-- Die Teile erben die Regel ihres Dokuments. `exists` statt `in`: der Planer kann den Index auf
-- `profile_dokument.id` benutzen, und die Bedingung bleibt lesbar.
drop policy if exists teil_lesen on public.profile_dokument_teil;
create policy teil_lesen on public.profile_dokument_teil
  for select to authenticated
  using (exists (select 1 from public.profile_dokument d
                  where d.id = dokument_id
                    and d.org_id = (select org_id from public.user_profiles where id = auth.uid())));

drop policy if exists teil_schreiben on public.profile_dokument_teil;
create policy teil_schreiben on public.profile_dokument_teil
  for all to authenticated
  using (exists (select 1 from public.profile_dokument d
                  where d.id = dokument_id and d.profil_id = auth.uid()))
  with check (exists (select 1 from public.profile_dokument d
                       where d.id = dokument_id and d.profil_id = auth.uid()));

-- ⚠ Supabase vergibt auf Funktionen in `public` per Default EXECUTE an anon UND authenticated,
-- und `revoke from public` reicht dafuer NICHT (Auto-Memory `govisor-rpc-execute-grants`; 0030
-- schloss so ein Loch in der Produktion). Diese Migration legt bewusst KEINE Funktion an. Wer
-- hier spaeter eine ergaenzt, entzieht beiden Rollen EXECUTE einzeln.

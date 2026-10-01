-- Stufe und Abo-Status an die ORGANISATION, additiv. Preismodell v1.9 §2/§13.
-- Entwurf und Begründung: docs/preismodell-schema-v1.9.md
--
-- WARUM. `getTier()` las bis heute `user_profiles.plan` — die Stufe hing also am NUTZER,
-- während Abo, Seats und Profile an der Organisation hängen (0024). Zwei Quellen für eine
-- Aussage driften: wer im internen Kontenwerkzeug `organizations.plan` setzt, ändert am
-- Gating nichts, und ein Nutzer kann bezahlte Rechte tragen, die seine Organisation nicht
-- hat. Sven am 2026-10-01: „tier gehört nur an die organisation".
--
-- ⚠ WARUM `tier` UND `abo_status` GETRENNT. `plan` mischte zwei Dinge: WAS das Konto bekommt
-- und OB das Abo läuft. Bei zwei Stufen ging das. Ab vier nicht mehr — ein gekündigtes
-- Strategie-Konto wäre von einem gekündigten Analyse-Konto nicht unterscheidbar, und genau
-- diese Unterscheidung braucht jede Rückgewinnung und jede Proration.
--
-- ⚠ `plan` BLEIBT STEHEN und wird nicht entfernt. Dieselbe Dual-State-Vorsicht wie in 0024:
-- erst wenn aller Code auf `tier` liest, fällt die alte Spalte. Solange beides existiert,
-- ist `tier` die Wahrheit und `plan` nur noch Altbestand.

alter table public.organizations
  add column if not exists tier text not null default 'free'
    check (tier in ('trial','free','analyse','strategie')),
  add column if not exists abo_status text not null default 'aktiv'
    check (abo_status in ('aktiv','gekuendigt')),
  add column if not exists trial_ends_at timestamptz;

comment on column public.organizations.tier is
  'Was das Konto bekommt (Preismodell v1.9 §2). NICHT ob es laeuft — das ist abo_status. '
  'Einzige Quelle fuer getTier(); user_profiles.plan ist Altbestand.';
comment on column public.organizations.abo_status is
  'Laeuft das Abo. Bei ''gekuendigt'' gilt tier bis plan_until weiter (§5.5).';
comment on column public.organizations.trial_ends_at is
  'Ende der vier Wochen Vollzugang (§3a). Danach automatisch tier=''free''.';

-- ── Backfill ──────────────────────────────────────────────────────────────────────────────
--
-- ⛔ `plan='paid'` SAGT NICHT, WELCHE bezahlte Stufe gemeint ist — die Unterscheidung gab es
-- bis v1.6 nicht. Gemessen am 2026-10-01 über die REST-API: alle 15 Organisationen stehen auf
-- `plan='free'`, es gibt KEIN bezahltes Konto. Der Backfill ist damit eindeutig und muss
-- nichts raten.
--
-- Die Sperre unten ist für den Fall, dass zwischen heute und dem Einspielen jemand bezahlt:
-- dann bricht die Migration ab und verlangt eine Entscheidung, statt still `analyse` zu
-- vergeben. Eine geratene Stufe wäre entweder ein unbezahltes Recht oder ein bezahltes, das
-- der Kunde nicht bekommt — beides fällt erst bei der Beschwerde auf.
do $$
declare n_bezahlt int;
begin
  select count(*) into n_bezahlt from public.organizations where plan <> 'free';
  if n_bezahlt > 0 then
    raise exception
      'Abbruch: % Organisation(en) mit plan<>''free''. Welche Stufe (analyse/strategie) '
      'gilt je Konto? Erst festlegen, dann diesen Block anpassen und erneut einspielen. '
      'Liste: select id,name,plan,plan_until from organizations where plan <> ''free'';',
      n_bezahlt;
  end if;
end $$;

update public.organizations
   set tier = 'free', abo_status = 'aktiv'
 where plan = 'free';

-- ── Gegenprobe im selben Lauf ─────────────────────────────────────────────────────────────
-- Eine Migration, die nicht prueft, was sie angerichtet hat, ist eine Behauptung.
do $$
declare n_ohne int;
begin
  select count(*) into n_ohne from public.organizations where tier is null;
  if n_ohne > 0 then
    raise exception 'Backfill unvollstaendig: % Organisation(en) ohne tier', n_ohne;
  end if;
end $$;

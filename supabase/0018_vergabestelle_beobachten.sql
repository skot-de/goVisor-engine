-- Beobachtete Vergabestellen (Aktivierung D, 2026-09-01).
--
-- WARUM. Die Merkliste beobachtet einen VORGANG. Wer eine Vergabestelle im Blick behalten
-- will, musste bisher selbst nachsehen; das Übergabepapier nennt es unter „Bindung ohne
-- Datengewinn", und genau das ist es: es kostet nichts und hält jemanden im Produkt.
--
-- ⚠ OHNE DIE VORHERSAGE AUS DEM PAPIER. Dort steht „Diese Stelle schreibt etwa alle vier
-- Jahre aus. Sollen wir euch erinnern?". Am 2026-09-01 nachgemessen: `contract_succession`
-- meldet für JEDE grosse Vergabestelle einen Median-Abstand von 1,0 Jahren — das ist eine
-- Eigenschaft des Nachfolge-Modells (es verkettet Jahreswiederholungen), kein Vertragszyklus.
-- Weder `buyer_loyalty` noch `retender_signal` tragen eine Zykluslänge. Der Satz liesse sich
-- also nicht belegen, und eine erfundene Jahreszahl wäre genau die Sorte Behauptung, gegen
-- die dieses Produkt antritt. Die Beobachtung sagt deshalb nur zu, was sie halten kann:
-- Bescheid geben, wenn diese Stelle etwas ausschreibt.

create table if not exists public.user_buyer_watch (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  -- Der Name IST der Schlüssel. Eine Entitäts-ID wäre stabiler, aber der Lead-Export trägt
  -- sie nicht, und ein Join gegen Gold gibt es im Frontend nicht. Lieber ein Schlüssel, der
  -- gelegentlich zwei Schreibweisen trennt, als einer, den niemand füllen kann.
  buyer_key   text not null,
  buyer_name  text,
  created_at  timestamptz not null default now(),
  unique (user_id, buyer_key)
);

alter table public.user_buyer_watch enable row level security;

drop policy if exists "ubw_own" on public.user_buyer_watch;
create policy "ubw_own" on public.user_buyer_watch for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

create index if not exists ubw_user_idx on public.user_buyer_watch (user_id);

comment on table public.user_buyer_watch is
  'Beobachtete Vergabestellen. Speist den Posteingang; keine Vorhersage, nur „sagt Bescheid".';

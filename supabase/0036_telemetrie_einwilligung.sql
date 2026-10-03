-- 0036 — Telemetrie Stufe 2: Einwilligung, dauerhafte Besucherkennung, Kampagnen.
--
-- Sven am 2026-10-03: „bau es so, dass wir alles messen koennen und duerfen."
--
-- ⚠ DAS IST EIN ZWEISTUFIGES MODELL, KEIN SCHALTER. 0035 misst cookielos auf Grundlage
--   berechtigten Interesses: keine Kennung, keine Wiedererkennung, nichts Personenbezogenes.
--   Diese Migration legt eine ZWEITE Stufe darueber, die erst mit ausdruecklicher Einwilligung
--   greift. Jeder Besucher wird damit so weit gemessen, wie er es erlaubt — und niemand wird
--   gar nicht gemessen, bloss weil er den Hinweis wegklickt.
--
--   Der naheliegende Entwurf („ohne Einwilligung messen wir nichts") waere rechtlich
--   bequemer und praktisch schlechter: die Mehrheit willigt nicht ein, und dann faellt
--   genau die Zahl aus, um die es vor dem Start geht — wie viele Fremde kommen ueberhaupt
--   auf eine Landingpage. Die Gegenrichtung („wir messen alles und fragen nicht") ist keine
--   Option: `besucher` ist ein Wiedererkennungsmerkmal und braucht nach § 25 TDDDG eine
--   Einwilligung, unabhaengig davon, ob man es Cookie nennt.
--
-- ⚠ `einwilligung` WIRD JE ZEILE MITGESCHRIEBEN, nicht nur im Cookie. Zwei Gruende, beide
--   praktisch: ein Widerruf muss genau die Zeilen loeschen koennen, die unter Einwilligung
--   entstanden sind (Art. 7 Abs. 3 DSGVO), und bei einer Nachfrage muss man belegen koennen,
--   auf welcher Grundlage eine Zeile liegt. Steht die Grundlage nur im Cookie, ist sie nach
--   dem Widerruf weg — und damit auch der Beweis.

alter table public.gov_ereignisse
  -- Dauerhafte, zufaellige Besucherkennung aus einem Cookie. NUR mit Einwilligung gesetzt.
  -- ⚠ Das ist das einzige echte Wiedererkennungsmerkmal in dieser Tabelle. Alles andere
  --   hier ist entweder fluechtig (`sitzung`, stirbt mit dem Tab) oder nicht personenbezogen.
  add column if not exists besucher text,

  -- Auf welcher Rechtsgrundlage liegt diese Zeile?
  --   false = berechtigtes Interesse, cookielos (0035-Stufe)
  --   true  = ausdrueckliche Einwilligung (Stufe 2)
  add column if not exists einwilligung boolean not null default false,

  -- ⚠ GROBER CRAWLER-NAME, NICHT DER KENNUNGSTEXT. 0035 speicherte nur `ist_bot` als
  --   Wahrheitswert — und damit liess sich die wichtigste Frage der KI-Sichtbarkeit nicht
  --   beantworten: liest GPTBot die Grounding Page, kommt ClaudeBot auf die Landingpages?
  --   Googlebot von GPTBot zu unterscheiden ist der ganze Zweck. Ein Crawler ist keine
  --   Person, das Feld ist also unbedenklich; der volle User-Agent bleibt trotzdem draussen,
  --   weil er bei Menschen ein Fingerabdruck waere und hier nichts beitraegt.
  add column if not exists bot_art text,

  -- Kampagnenkennzeichnung aus der Adresse (`utm_*`). NUR mit Einwilligung.
  -- ⚠ Als DREI Spalten, nicht als jsonb: Quelle und Medium sind die Gruppierungsachsen jeder
  --   Kampagnenauswertung. In jsonb muesste jede Abfrage sie einzeln auspacken, und
  --   Tippfehler im Schluessel fallen nie auf.
  add column if not exists utm_quelle text,
  add column if not exists utm_medium text,
  add column if not exists utm_kampagne text,

  -- Voller Referrer. NUR mit Einwilligung — er traegt bei Suchmaschinen den Suchbegriff.
  -- `herkunft` (nur der Host) bleibt die Spalte fuer die cookielose Stufe.
  add column if not exists referrer_voll text,

  -- Grobe Browser- und Geraeteklasse. NUR mit Einwilligung.
  -- ⚠ Die Geraeteklasse liesse sich auch aus `viewport_w` ableiten, und das tut die
  --   cookielose Stufe. Hier steht die genauere Angabe aus dem User-Agent.
  add column if not exists browser text,
  add column if not exists geraet text;

comment on column public.gov_ereignisse.besucher is
  'Dauerhafte Zufallskennung aus Cookie. NUR mit Einwilligung (§ 25 TDDDG). Das einzige '
  'Wiedererkennungsmerkmal der Tabelle.';
comment on column public.gov_ereignisse.einwilligung is
  'Rechtsgrundlage DIESER Zeile: false = berechtigtes Interesse cookielos, true = '
  'Einwilligung. Je Zeile mitgeschrieben, damit ein Widerruf (Art. 7 Abs. 3 DSGVO) genau '
  'die betroffenen Zeilen treffen kann und die Grundlage belegbar bleibt.';
comment on column public.gov_ereignisse.bot_art is
  'Grober Crawler-Name (googlebot, gptbot, claudebot, …), abgeleitet bei der Erfassung. '
  'Beantwortet, WELCHER Abrufer kommt — ist_bot allein konnte das nicht.';

create index if not exists gov_ereignisse_besucher_idx on public.gov_ereignisse (besucher)
  where besucher is not null;
create index if not exists gov_ereignisse_bot_art_idx on public.gov_ereignisse (bot_art)
  where bot_art is not null;
create index if not exists gov_ereignisse_kampagne_idx on public.gov_ereignisse (utm_quelle, utm_kampagne)
  where utm_quelle is not null;

-- ── WIDERRUF ────────────────────────────────────────────────────────────────────────────
-- Art. 7 Abs. 3 DSGVO: eine Einwilligung ist jederzeit widerrufbar, und der Widerruf muss so
-- einfach sein wie die Erteilung. Praktisch heisst das: es braucht einen Weg, der die unter
-- Einwilligung entstandenen Zeilen EINES Besuchers entfernt.
--
-- ⚠ LOESCHT NUR, WAS UNTER EINWILLIGUNG ENTSTAND (`einwilligung = true`). Die cookielosen
--   Zeilen derselben Person sind nicht zuordenbar — sie tragen keine Besucherkennung — und
--   liegen auf anderer Rechtsgrundlage. Sie mitzuloeschen waere nicht nur unmoeglich,
--   sondern auch nicht verlangt.
create or replace function public.gov_einwilligung_widerrufen(besucher_kennung text)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare geloescht integer;
begin
  if besucher_kennung is null or length(besucher_kennung) < 8 then
    raise exception 'Besucherkennung fehlt oder ist zu kurz';
  end if;
  delete from public.gov_ereignisse
   where besucher = besucher_kennung and einwilligung;
  get diagnostics geloescht = row_count;
  return geloescht;
end;
$$;

revoke all on function public.gov_einwilligung_widerrufen(text) from public, anon, authenticated;
grant execute on function public.gov_einwilligung_widerrufen(text) to service_role;

comment on function public.gov_einwilligung_widerrufen(text) is
  'Loescht die unter Einwilligung erhobenen Zeilen eines Besuchers (Art. 7 Abs. 3 DSGVO). '
  'Cookielose Zeilen bleiben: sie tragen keine Kennung und liegen auf anderer Grundlage.';

-- ── AUSWERTUNGS-SICHTEN ─────────────────────────────────────────────────────────────────
-- ⚠ DIESE SICHTEN LOESEN EINEN ECHTEN ZAEHLFEHLER, keine Bequemlichkeit.
--
--   Es gibt genau EIN Layout, also erbt auch die oeffentliche Ausschreibungsseite den
--   Telemetrie-Provider. Ein Mensch erzeugt deshalb ZWEI `seite_gesehen`-Zeilen — eine
--   serverseitig (ohne `sitzung`) und eine im Browser (mit `sitzung`) —, ein Crawler nur
--   eine. Wer `seite_gesehen` naiv zaehlt, hat die doppelte Menschenzahl.
--
--   Unterscheidbar ist das an `sitzung is null`, aber darauf zu bauen, dass jede kuenftige
--   Abfrage daran denkt, ist dieselbe Wette, die bei `ist_bot` schon verloren wurde. Die
--   Regel gehoert EINMAL hierher.
create or replace view public.gov_seitenaufrufe as
  select * from public.gov_ereignisse
   where art = 'seite_gesehen' and not ist_bot and sitzung is not null;

comment on view public.gov_seitenaufrufe is
  'Menschliche Seitenaufrufe, genau einmal gezaehlt: Browser-Zeilen (sitzung gesetzt), Bots '
  'heraus. Die serverseitigen Zeilen desselben Aufrufs sind absichtlich NICHT dabei — sie '
  'wuerden jeden Menschen doppelt zaehlen.';

create or replace view public.gov_crawler_besuche as
  select * from public.gov_ereignisse
   where art = 'seite_gesehen' and ist_bot and sitzung is null;

comment on view public.gov_crawler_besuche is
  'Crawler-Aufrufe aus der serverseitigen Erfassung. `bot_art` sagt, welcher Abrufer — das '
  'ist die Kennzahl der KI-Sichtbarkeit.';

revoke all on table public.gov_seitenaufrufe from public, anon, authenticated;
revoke all on table public.gov_crawler_besuche from public, anon, authenticated;

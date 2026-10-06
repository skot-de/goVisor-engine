-- 0035 — Telemetrie: eine eigene Ereignis-Senke, kein Drittanbieter.
--
-- WOZU. Bis heute gibt es `web/lib/analytics.ts` (Ticket #8) mit neun Ereignissen und acht
-- Aufrufstellen, aber keine Senke: der PostHog-Zweig ist tot (keine Abhaengigkeit, keine
-- Initialisierung), und die zweite Senke ist ein Ring-Puffer `window.__gvEvents` mit 200
-- Eintraegen, der beim Schliessen des Tabs verschwindet. Gemessen wurde also noch nie etwas,
-- ausser Lead-Klicks in `user_lead_interactions`. Diese Tabelle schliesst das.
--
-- ⚠ WARUM EIGENE SENKE UND NICHT GA4/PostHog. Entscheidung Sven, 2026-10-02. Kein
-- Drittanbieter heisst: keine Uebermittlung in die USA, keine Cookies, kein
-- Zustimmungsbanner. Das ist nicht nur rechtlich bequemer — ein Banner auf den
-- SEO-Landingpages wuerde genau das beschaedigen, worum es bei Ticket 17 geht.
--
-- ⚠ ZWEI ENTSCHEIDUNGEN, DIE SPAETER NICHT MEHR KORRIGIERBAR SIND, weil fehlende Daten
--   nicht nachtraeglich entstehen und zu viel erfasste Daten nicht nachtraeglich verschwinden:
--
--   1. KEINE IP-ADRESSE, KEIN VOLLER USER-AGENT, KEIN VOLLER REFERRER. Die IP ist ein
--      personenbezogenes Datum und wird fuer keine der Fragen gebraucht, die Sven gestellt
--      hat. Vom Referrer wird nur der HOST gespeichert: ein vollstaendiger Referrer traegt
--      bei Suchmaschinen den Suchbegriff, und das ist fremder Personenbezug.
--   2. `sitzung` IST KEIN COOKIE. Der Client erzeugt je Tab eine Zufallskennung in
--      `sessionStorage`. Sie ueberlebt den Tab nicht, folgt dem Nutzer nicht ueber Seiten
--      hinweg wiedererkennbar und existiert nicht auf anderen Websites. Damit laesst sich
--      „wie lange war jemand auf welcher Seite" beantworten, OHNE ein Wiedererkennungs-
--      merkmal anzulegen.

create table if not exists public.gov_ereignisse (
  id           bigserial primary key,
  erfasst_at   timestamptz  not null default now(),

  -- Zufallskennung je Tab (sessionStorage), NICHT personenbezogen, NICHT wiederkehrend.
  -- ⚠ NULLABLE, und das ist kein Versehen: die serverseitige Erfassung der oeffentlichen
  --   Seiten laeuft OHNE Javascript (Bedingung von Ticket 17: Googlebot muss exakt dasselbe
  --   HTML bekommen, also kein Zaehlpixel und kein zusaetzliches Script-Tag). Dort gibt es
  --   keinen sessionStorage und damit keine Sitzung. Eine Platzhalterkennung waere schlimmer
  --   als NULL: sie saehe wie eine echte Sitzung aus und wuerde Sitzungszahlen aufblaehen.
  sitzung      text,

  -- Nur gesetzt, wenn jemand angemeldet ist. Anonymer Verkehr ist der interessante Teil
  -- vor dem Start, deshalb ausdruecklich nullable.
  nutzer_id    uuid         references auth.users (id) on delete set null,
  org_id       uuid,

  art          text         not null,          -- Ereignisname, s. EV in web/lib/analytics.ts
  pfad         text,                           -- Route OHNE Query-String (s. unten)
  props        jsonb        not null default '{}'::jsonb,

  -- Verweildauer und Scrolltiefe gehoeren zum Seitenaufruf-Ereignis, nicht zu jedem Klick.
  dauer_ms     integer      check (dauer_ms is null or dauer_ms between 0 and 86400000),
  tiefe_pct    smallint     check (tiefe_pct is null or tiefe_pct between 0 and 100),

  -- Klickkarte: WELCHES ELEMENT, nicht welcher Bildpunkt und nicht welcher Text.
  -- ⚠ `ziel_text` gibt es bewusst NICHT. Auf den App-Seiten stehen Vergabedaten; ein
  --   Klickziel-Text haette Lead-Inhalte in diese Tabelle getragen, und das faengt man
  --   spaeter nicht mehr ein. Fuer Heatmaps genuegt das Element plus die relative Position
  --   IN ihm.
  ziel         text,                           -- stabiler Selektor / data-mess-Attribut
  ziel_x_pct   smallint     check (ziel_x_pct is null or ziel_x_pct between 0 and 100),
  ziel_y_pct   smallint     check (ziel_y_pct is null or ziel_y_pct between 0 and 100),

  viewport_w   smallint     check (viewport_w is null or viewport_w between 0 and 20000),
  viewport_h   smallint     check (viewport_h is null or viewport_h between 0 and 20000),

  -- NUR der Host, nie die vollstaendige Adresse. Siehe Entscheidung 1 oben.
  herkunft     text,

  -- ⚠ EIGENE SPALTE, NICHT IN `props`, UND NOT NULL. Die oeffentlichen Landingpages SIND
  --   ein SEO-Kanal, Googlebot und Co. sind dort der erwartete Hauptverkehr. Eine
  --   ungefilterte Trichterzahl ist deshalb nicht bloss unscharf, sie ist nach OBEN
  --   verzerrt: sie sieht nach Erfolg aus, wo keiner ist. Als Spalte mit Index und
  --   Vorgabewert ist das Filtern billig und das VERGESSEN schwer; in `props` versteckt
  --   haette es jede Abfrage einzeln mitdenken muessen.
  -- Die Erkennung passiert bei der ERFASSUNG (User-Agent), nicht bei der Auswertung —
  -- der User-Agent selbst wird dabei NICHT gespeichert, nur dieses Urteil.
  ist_bot      boolean      not null default false
);

comment on table public.gov_ereignisse is
  'Eigene Telemetrie-Senke (0035). Keine IP, kein voller User-Agent, kein voller Referrer, '
  'kein Cookie. `sitzung` ist eine Zufallskennung je Tab aus sessionStorage.';
comment on column public.gov_ereignisse.pfad is
  'Route OHNE Query-String. Ein Query-String kann personenbezogene Parameter tragen; die '
  'Normalisierung passiert im Client UND erneut in /api/ereignis (zwei Tore, s. Route).';
comment on column public.gov_ereignisse.ziel is
  'Stabiler Selektor oder data-mess-Attribut des geklickten Elements. ABSICHTLICH kein '
  'Elementtext: auf App-Seiten stehen Vergabedaten.';

-- ⚠ `ist_bot` steht in den Zeit-Indizes VORNE. Jede ehrliche Auswertung filtert darauf,
--   also soll der Index sie genau so unterstuetzen. Wer ohne diesen Filter auswertet, misst
--   Googlebot.
create index if not exists gov_ereignisse_art_zeit_idx  on public.gov_ereignisse (ist_bot, art, erfasst_at desc);
create index if not exists gov_ereignisse_pfad_zeit_idx on public.gov_ereignisse (ist_bot, pfad, erfasst_at desc);
create index if not exists gov_ereignisse_sitzung_idx   on public.gov_ereignisse (sitzung)
  where sitzung is not null;
create index if not exists gov_ereignisse_nutzer_idx    on public.gov_ereignisse (nutzer_id)
  where nutzer_id is not null;

comment on column public.gov_ereignisse.ist_bot is
  'Urteil aus dem User-Agent BEI DER ERFASSUNG. Der User-Agent selbst wird nicht gespeichert. '
  'Jede Auswertung muss darauf filtern, sonst zaehlt sie Suchmaschinen-Crawler als Interessenten.';

-- ── RECHTE ──────────────────────────────────────────────────────────────────────────────
-- ⚠ NIEMAND SCHREIBT HIER DIREKT HINEIN, auch nicht `authenticated`. Der Weg ist
--   /api/ereignis mit dem Service-Schluessel, und zwar aus zwei Gruenden:
--     a) Nur so lassen sich die Werte serverseitig pruefen und beschneiden (Query-String
--        abschneiden, Referrer auf den Host kuerzen, Ereignisnamen gegen eine Liste pruefen).
--        Ein Client, der direkt in die Tabelle schreibt, kann alles hineinschreiben.
--     b) Eine Ereignistabelle, die `anon` LESEN kann, gibt fremdes Verhalten heraus.
--
-- ⚠ RLS ohne Policy reicht NICHT. Supabase vergibt per Vorgabe Tabellenrechte an `anon`
--   und `authenticated`, und `revoke ... from public` nimmt diese benannten Rollen NICHT
--   mit — dieselbe Falle, die 0030 bei den Funktionsrechten geschlossen hat. Deshalb hier
--   ausdruecklich beide Rollen entziehen.
alter table public.gov_ereignisse enable row level security;

revoke all on table public.gov_ereignisse from public, anon, authenticated;
revoke all on sequence public.gov_ereignisse_id_seq from public, anon, authenticated;

-- ── AUFBEWAHRUNG ────────────────────────────────────────────────────────────────────────
-- Speicherbegrenzung ist kein Hausputz, sondern Pflicht (DSGVO Art. 5 Abs. 1 lit. e). 180
-- Tage reichen fuer Jahresvergleiche der Trichter-Quoten; Rohklicks braucht niemand laenger.
-- ⚠ Diese Funktion raeumt NICHT von selbst auf. Sie muss gerufen werden — der Nachtlauf
--   tut das (scripts/daily_leads.sh). Wer das vergisst, sammelt unbegrenzt.
create or replace function public.gov_ereignisse_aufraeumen(tage integer default 180)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare geloescht integer;
begin
  delete from public.gov_ereignisse
   where erfasst_at < now() - make_interval(days => greatest(tage, 1));
  get diagnostics geloescht = row_count;
  return geloescht;
end;
$$;

-- Gleiche Haertung wie 0030/0031: Vorgabe-EXECUTE fuer anon und authenticated entziehen.
revoke all on function public.gov_ereignisse_aufraeumen(integer) from public, anon, authenticated;

-- ⚠ UND AUSDRUECKLICH DEM SERVICE-SCHLUESSEL GEWAEHREN — gleiche Konvention wie 0030 bei
--   `kauf_gutschreiben` und `vorgang_freischalten`. Technisch kaeme der Service-Schluessel
--   auch ohne diesen Grant durch (er umgeht Grants; nachgemessen: der Nachtlauf-Aufruf
--   funktionierte vorher). Der Grant steht hier, weil er die ABSICHT festhaelt: „nur der
--   Server, aber der soll". Ohne ihn ist von aussen nicht unterscheidbar, ob eine Funktion
--   bewusst servergebunden oder versehentlich unaufrufbar gehaertet wurde — und genau das
--   prueft `tests/test_rpc_rechte.py::test_jede_rpc_hat_danach_einen_erlaubten_aufrufer`.
grant execute on function public.gov_ereignisse_aufraeumen(integer) to service_role;

comment on function public.gov_ereignisse_aufraeumen(integer) is
  'Loescht Ereignisse aelter als `tage` (Vorgabe 180, DSGVO Art. 5 Abs. 1 lit. e). Nur fuer '
  'den Service-Schluessel; wird vom Nachtlauf gerufen.';

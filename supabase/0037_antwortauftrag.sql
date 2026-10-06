-- 0037 — Antwortauftrag: der Knopf, der aus Fragebogen plus Bausteinen Entwuerfe macht.
--
-- WOZU. Funktion 1 der Go-live-Liste. Der Kunde laedt den Fragebogen der Vergabestelle hoch,
-- bekommt je Frage einen Entwurf aus seinen eigenen Textbausteinen, prueft und gibt frei. Die
-- Luecke gegen BidFix ("Abgabeordner zu 90 % vorbereitet") war nie das Fundament: Bausteine,
-- Checkliste und Upload-Feld sind seit Wochen da, es fehlte die Verbindung.
--
-- ⚠ WARUM EIN AUFTRAG UND KEINE ANFRAGE-ANTWORT. Die Erzeugung laeuft in Python, weil die
-- Geldwache in `llm.chat()` sitzt und nicht im Aufrufer (Auto-Memory `govisor-geldwache`). Eine
-- Next-Route, die selbst bei OpenRouter anklopft, umgeht Kontostand, Tagesbuch und Deckel. Der
-- naheliegende Weg waere `spawn python3` gewesen wie in `web/app/api/draft-check/route.ts` --
-- aber das ist genau eine der Routen, die NICHT serverless-faehig sind, und aus vier wuerden
-- fuenf. Ein Bogen mit zwoelf Fragen dauert ausserdem laenger, als eine Anfrage sinnvoll offen
-- bleibt. Also: die Route legt einen Auftrag ab, `scripts/antwort_arbeiter.py` rechnet, die
-- Oberflaeche fragt das Ergebnis ab. Entscheidung Sven, 2026-10-04.
--
-- ⚠ ZWEI DINGE, DIE VERSCHLUESSELT GEHOEREN, UND EINES, DAS NICHT.
--   Verschluesselt: der Fragebogen (er traegt die Anforderungen der Vergabestelle) und das
--   Ergebnis (es traegt die Angebotstexte des Kunden, also sein Kapital). Beides mit demselben
--   Umschlagverfahren wie `profile_text_blocks.content_encrypted` (§12.3). Es waere absurd, die
--   Bausteine zu verschluesseln und die daraus gebauten Antworten eine Tabelle weiter offen
--   liegen zu lassen.
--   NICHT verschluesselt: `zaehlung`. Darin stehen nur Zahlen ("7 fertig, 3 unbelegt, 2 ohne
--   Baustein"). Die Oberflaeche muss den Fortschritt zeigen koennen, ohne zu entschluesseln,
--   und der Betrieb muss sehen, ob Auftraege durchlaufen. Ein verschluesselter Zaehler haette
--   nur Nachteile.
--
-- ⚠ `versuche` IST EINE GELDBREMSE, KEIN KOMFORT. Die Arbeiter pausieren nie (Auto-Memory
--   `govisor-speicherwand`). Ein Auftrag, der nach dem LLM-Aufruf scheitert, wuerde bei jedem
--   Durchlauf erneut Geld kosten. Der Arbeiter zaehlt deshalb HOCH, BEVOR er das Modell fragt,
--   und bei 3 ist Schluss. Wer diese Reihenfolge umdreht, baut eine Kostenschleife.

create table if not exists public.user_antwortauftrag (
  id                   uuid primary key default gen_random_uuid(),
  org_id               uuid        not null,
  -- WESSEN Bausteine der Arbeiter lesen soll.
  -- ⚠ ZWEI DINGE HEISSEN HIER FAST GLEICH, und sie zu verwechseln heisst, dass der Arbeiter
  --   nichts findet:
  --     `user_profiles.id`  IST die Auth-Nutzerkennung (0001: `references auth.users(id)`), und
  --                         `profile_text_blocks.profile_id` zeigt genau darauf — die
  --                         Weboberflaeche setzt dort `user.id` (s. web/app/api/blocks/route.ts).
  --                         **Bausteine haengen also am NUTZER.**
  --     `profiles.id`       sind die Mehrfachprofile aus 0033, auf die `active_profile_id`
  --                         zeigt. Mit Bausteinen haben sie NICHTS zu tun.
  --   Darum zeigt dieses Feld auf `user_profiles` und heisst nicht `profiles`. Ein zusaetzliches
  --   `nutzer_id` stand hier zuerst und ist ersatzlos weg: es waere dieselbe Person mit anderer
  --   Loeschregel gewesen, also eine Einladung, die falsche von beiden zu lesen.
  profil_id            uuid        not null references public.user_profiles (id) on delete cascade,
  -- Der Vorgang, zu dem der Bogen gehoert. Nullable: ein Bogen darf auch ohne Lead hochgeladen
  -- werden (jemand probiert die Funktion an einem alten Angebot aus).
  lead_id              text,
  dateiname            text,
  status               text        not null default 'offen'
                                   check (status in ('offen', 'laeuft', 'fertig', 'fehler')),
  -- Der ausgelesene TEXT des Bogens, nicht die Datei. Wir halten keine Uploads: weniger
  -- Angriffsflaeche, kein Blob-Speicher, und der Text ist alles, was die Erzeugung braucht.
  fragebogen_encrypted bytea       not null,
  ergebnis_encrypted   bytea,
  zaehlung             jsonb,
  fragen_gesamt        integer,
  fehler               text,
  versuche             smallint    not null default 0 check (versuche >= 0),
  erstellt_at          timestamptz not null default now(),
  geholt_at            timestamptz,
  fertig_at            timestamptz
);

-- Der Arbeiter fragt genau eine Sache: was ist offen, aeltestes zuerst.
create index if not exists user_antwortauftrag_offen_idx
  on public.user_antwortauftrag (status, erstellt_at)
  where status in ('offen', 'laeuft');

create index if not exists user_antwortauftrag_org_idx
  on public.user_antwortauftrag (org_id, erstellt_at desc);

comment on table public.user_antwortauftrag is
  'Antwortvorschlaege zu einem Fragebogen (Funktion 1 Go-live). Die Route legt ab, '
  'scripts/antwort_arbeiter.py rechnet, die Oberflaeche fragt ab. Fragebogen und Ergebnis '
  'verschluesselt wie profile_text_blocks; zaehlung bewusst im Klartext (nur Zahlen).';

comment on column public.user_antwortauftrag.versuche is
  'Geldbremse: der Arbeiter zaehlt HOCH, BEVOR er das Modell fragt, und gibt bei 3 auf. '
  'Andere Reihenfolge = Kostenschleife, weil die Arbeiter nie pausieren.';

-- ── Zugriff ─────────────────────────────────────────────────────────────────────────────────
-- RLS: der Nutzer sieht die Auftraege SEINER Organisation und legt nur dort ab. Der Arbeiter
-- laeuft mit dem Service-Key und umgeht RLS ohnehin — er braucht keine Policy, und ihm eine zu
-- geben wuerde nur verschleiern, wer hier wirklich darf.
alter table public.user_antwortauftrag enable row level security;

-- ⚠ Die Form ist aus 0027 uebernommen und nicht neu erfunden: `user_profiles.id` IST die
--   Auth-Kennung, es gibt dort KEIN `user_id`. Eine Bedingung auf `p.user_id = auth.uid()` stand
--   hier zuerst und waere beim Anwenden an einer nicht existierenden Spalte gescheitert.
drop policy if exists antwortauftrag_lesen on public.user_antwortauftrag;
create policy antwortauftrag_lesen on public.user_antwortauftrag
  for select to authenticated
  using (org_id = (select org_id from public.user_profiles where id = auth.uid()));

drop policy if exists antwortauftrag_anlegen on public.user_antwortauftrag;
create policy antwortauftrag_anlegen on public.user_antwortauftrag
  for insert to authenticated
  with check (org_id = (select org_id from public.user_profiles where id = auth.uid())
              and profil_id = auth.uid());

-- ⚠ KEIN update UND KEIN delete FUER `authenticated`. Den Status setzt ausschliesslich der
-- Arbeiter. Duerfte der Nutzer schreiben, koennte er `versuche` zuruecksetzen — und damit genau
-- die Geldbremse aushebeln, die oben beschrieben ist.
revoke update, delete on public.user_antwortauftrag from authenticated;

-- ⚠ Supabase vergibt auf Funktionen in `public` per Default EXECUTE an anon UND authenticated,
-- und `revoke from public` reicht dafuer NICHT (Auto-Memory `govisor-rpc-execute-grants`, 0030
-- schloss so ein Loch in der Produktion). Diese Migration legt bewusst KEINE Funktion an. Wer
-- hier spaeter eine ergaenzt, entzieht beiden Rollen EXECUTE einzeln.

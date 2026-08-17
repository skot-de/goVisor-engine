-- Impressum-Nachweise: gehört diese Domain dieser Firma?
--
-- WOZU. Der Impressum-Prüfer (govisor/impressum.py, web/lib/impressum.ts) entscheidet
-- beim Onboarding, ob die Mail-Domain eines Nutzers zu der Firma gehört, auf deren Profil
-- er landet. Bis hierher verdampfte dieses Urteil: die Route schrieb nichts, und der
-- Hauptweg („Ja, das sind wir") warf es beim Seitenwechsel weg. Damit fehlte uns
--   1. der Beleg, WARUM jemand Zugriff auf ein fremdes Firmenprofil bekam,
--   2. ein Cache — jede Registrierung holte dieselben bis zu 15 Seiten neu,
--   3. eine Datenquelle, die wir sonst nirgends haben (zu 47 % unserer Firmen kennen
--      wir keine Domain; hier verifizieren wir genau diese Zuordnung).
--
-- KEIN PERSONENBEZUG. Gespeichert wird die FIRMENDOMAIN und das Urteil, nicht die
-- Mailadresse und nicht, wer sich registriert hat. Wer das später zusammenführen will,
-- muss es über `identity_claims` tun, wo die Zuordnung bewusst und mit RLS liegt.
-- Diese Tabelle ist eine Aussage über Firmen, nicht über Menschen.

create table if not exists public.domain_proof (
  domain        text        not null,
  identity_id   text        not null,
  -- belegt | widerlegt | nicht_pruefbar. Drei Urteile, nicht zwei: „nicht prüfbar" ist
  -- KEIN „widerlegt" — gemessen scheitern Firmen an kaputten Zertifikaten ihres eigenen
  -- Hosters, und wer das als Widerlegung bucht, sperrt echte Kunden aus.
  urteil        text        not null check (urteil in ('belegt','widerlegt','nicht_pruefbar')),
  quote         real,
  pfad          text,
  ort_belegt    boolean     not null default false,
  register_belegt boolean   not null default false,
  -- Woher der Nachweis stammt: aus einer Registrierung oder aus einem Stapellauf.
  quelle        text        not null default 'registrierung',
  sekunden      real,
  geprueft_am   timestamptz not null default now(),
  primary key (domain, identity_id)
);

create index if not exists domain_proof_identity on public.domain_proof (identity_id);
-- Für den Cache-Zugriff: „was wissen wir über diese Domain, und wie alt ist es?"
create index if not exists domain_proof_alter on public.domain_proof (geprueft_am desc);

alter table public.domain_proof enable row level security;

-- KEINE Policy für `authenticated`, und das ist Absicht.
--
-- Die Tabelle ordnet Domains zu Firmen zu. Wäre sie lesbar, könnte jeder angemeldete
-- Nutzer die Kontaktdomains unseres gesamten Firmenbestands abgreifen — dasselbe Leck,
-- das `suppliers.domain` schon serverseitig hält (siehe web/lib/suppliers.ts). Zugriff
-- ausschliesslich über den Secret-Key im Server, der RLS umgeht.
--
-- Ohne Policy und mit aktivem RLS ist die Tabelle für anon und authenticated leer.

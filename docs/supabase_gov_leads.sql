-- goVisor Frontend-Tabelle: eine Zeile je Lead (aus gold.build_lead_export).
-- Einmalig im Supabase-Dashboard → SQL Editor ausführen.
create table if not exists gov_leads (
  lead_id           text primary key,
  titel             text,
  buyer             text,
  buyer_town        text,
  cpv               text,
  cpv_label         text,
  nuts_full         text,
  nuts1             text,
  region            text,
  art               text,
  phase             text,          -- auslauf | f02 | f01
  neu               boolean,
  natur_kat         text,          -- dienst | liefer | bau
  volumen_wert      double precision,
  volumen_band      text,
  volumen_src       text,          -- echt | schaetz | unbekannt
  months_to_expiry  integer,
  faellig_basis     text,
  timing_warn       boolean,
  timing_src        text,          -- echt | schaetz | unsicher | unbekannt
  incumbent_name    text,
  incumbent_seit    integer,
  incumbent_conf    real,
  incumbent_src     text,          -- echt | unsicher
  wechsel           text,          -- hoch | mittel | niedrig | na
  num_tenders       integer,
  single_bidder     boolean,
  konk_stufe        text,          -- gering | mittel | hoch | na
  konk_src          text,
  ted_url           text,
  has_cmp           boolean,
  has_contracts     boolean,
  updated_at        timestamptz default now()
);
create index if not exists gov_leads_phase_idx  on gov_leads (phase);
create index if not exists gov_leads_nuts1_idx  on gov_leads (nuts1);
create index if not exists gov_leads_nuts_idx   on gov_leads (nuts_full);
create index if not exists gov_leads_natur_idx  on gov_leads (natur_kat);
create index if not exists gov_leads_band_idx   on gov_leads (volumen_band);
-- Row Level Security: Frontend liest nur; aktivieren + Read-Policy je nach Auth-Setup.
alter table gov_leads enable row level security;

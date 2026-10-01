# Schema für Preismodell v1.9 — Entwurf, nicht angewendet

**Stand:** 2026-10-01 · **Grundlage:** `INPUT/govisor-preismodell.md` v1.9, §5.2 / §7.3 / §13
**Status:** §2 und §3 sind **gebaut und eingespielt** (`0028` und `0032` am 2026-10-01 über
`scripts/migrate.py`, `getTier` umgestellt). §4 (Preistabelle) ist weiter Vorschlag.

Gegengeprüft nach dem Einspielen:

| | |
|---|---|
| Spalten | `tier`, `abo_status` (`text`, Default `free`/`aktiv`), `trial_ends_at` (`timestamptz`) |
| Prüfbedingungen | `tier ∈ (trial, free, analyse, strategie)` · `abo_status ∈ (aktiv, gekuendigt)` |
| Backfill | 13 Organisationen, alle `tier='free'`, `abo_status='aktiv'`, 0 ohne `tier` |
| Abfrage aus `tier.ts` | löst auf, Einbettung liefert die Organisation als Objekt |

⚠ `PAYWALL_ENFORCED` scharfzuschalten ist jetzt technisch möglich, aber eine
PRODUKTentscheidung: alle 13 Konten stehen auf `free`, es bekäme also jeder den
Free-Umfang.

---

## 1. Was v1.9 verlangt und was schon da ist

Die gute Nachricht zuerst: **`profile_package` und `profile_limit` haben in der Datenbank
nie existiert.** Die Staffel stand nur im Dokument. Das Streichen ist für das Schema ein
Nullvorgang — es gibt nichts zu entfernen.

Mehr noch: das Zwei-Achsen-Modell von v1.9 ist in `0024_organizations_profiles.sql`
(seit 2026-09-30 auf Prod, 13 Nutzer migriert) **bereits angelegt**. `seats_paid` und
`profiles_paid` sind genau „ein Preisobjekt mit Menge", zweimal. v1.9 liegt damit näher an
der Datenbank als v1.7 lag.

Die Namen weichen allerdings durchgehend ab. §13 nennt Felder, die so nicht heissen:

| §13 nennt | Prod heisst | Bewertung |
|---|---|---|
| `accounts` | `public.organizations` | nur Benennung, **nicht umbenennen** |
| `seat_count` | `organizations.seats_paid` | nur Benennung |
| `company_profile_count` | `organizations.profiles_paid` | nur Benennung, aber ⚠ Semantik wechselt (§3) |
| `company_profiles` | `public.profiles` | nur Benennung |
| `profile_type` | `profiles.profile_type` | ✅ fertig, inkl. Check |
| `tier` ∈ 4 Werte | `organizations.plan` ∈ 3 Werte | ⛔ **echte Änderung** (§2) |
| `trial_ends_at` | fehlt (nur `plan_until`) | ⛔ fehlt |
| `user_profile_assignments` | fehlt (`active_profile_id` = genau 1) | ⛔ Lücke in §7.1 |
| `vorgang_credits`, `unlocked_leads` | fehlt vollständig | ⛔ fehlt (§4.3) |
| Einzelpreis konfigurierbar | nirgends | ⛔ fehlt (§4) |

**Umbenennen empfehle ich nicht.** Die Tabellen tragen seit einem Tag Produktionsdaten, und
`organizations`/`profiles` sind die treffenderen Namen: ein Konto IST die Organisation. Statt
die Datenbank dem Dokument anzupassen, sollte §13 die echten Namen nennen.

---

## 2. Stufe und Status trennen — die eine strukturelle Änderung

`plan text check (plan in ('free','paid','cancelled'))` mischt zwei Dinge: **was der Kunde
bekommt** und **ob das Abo läuft**. Das ging bei zwei Stufen gerade noch. Mit vier geht es
nicht mehr: ein gekündigtes Strategie-Konto ist von einem gekündigten Analyse-Konto nicht
unterscheidbar, und genau diese Unterscheidung braucht jede Rückgewinnung und jede
Proration.

```sql
alter table public.organizations
  add column if not exists tier text not null default 'free'
    check (tier in ('trial','free','analyse','strategie')),
  add column if not exists abo_status text not null default 'aktiv'
    check (abo_status in ('aktiv','gekuendigt')),
  add column if not exists trial_ends_at timestamptz;

comment on column public.organizations.tier is
  'Was das Konto bekommt (§2 Preismodell). NICHT ob es laeuft — das ist abo_status.';
comment on column public.organizations.abo_status is
  'Laeuft das Abo. Bei gekuendigt gilt tier bis plan_until weiter (§5.5).';
comment on column public.organizations.trial_ends_at is
  'Ende der vier Wochen Vollzugang (§3a). Danach automatisch tier=free.';
```

Backfill aus dem heutigen Bestand, verlustfrei und ohne Annahme:

```sql
update public.organizations set
  tier = case when plan = 'free' then 'free'
              else 'analyse' end,          -- ⚠ ENTSCHEIDUNG, siehe unten
  abo_status = case when plan = 'cancelled' then 'gekuendigt' else 'aktiv' end
where tier = 'free' and plan <> 'free';
```

> ⚠ **Hier braucht es eine Entscheidung, keine Annahme.** `plan='paid'` sagt nicht, welche
> der beiden bezahlten Stufen gemeint ist, weil es die Unterscheidung bisher nicht gab. Alle
> Bestandskonten auf `analyse` zu setzen ist die vorsichtige Wahl (die billigere Stufe, also
> kein unbezahltes Recht), aber falsch, wenn jemand für Strategie bezahlt hat. **Vor dem
> Backfill die Liste der bezahlten Konten durchgehen.** Es sind wenige.

`plan` bleibt zunächst stehen und wird nicht gelesen. Entfernen erst, wenn der Code auf
`tier` umgestellt ist — dieselbe Dual-State-Vorsicht, mit der 0024 gebaut wurde.

### ✅ Erledigt: es gab zwei Plan-Spalten, die Abrechnung sass auf der falschen

`web/lib/tier.ts:34` liest **`user_profiles.plan`**, nicht `organizations.plan`. Das Gating
hängt also am Nutzer, die Abrechnung soll an der Organisation hängen. Solange beides
existiert, driften sie: ein Kontowechsel auf Strategie ändert nichts am Gating, und ein
Nutzer kann bezahlte Rechte haben, die seine Organisation nicht hat.

Sven am 2026-10-01: *„tier gehört nur an die organisation, stell getTier darauf um."*
Umgesetzt. `getTier()` liest jetzt in **einem** Rundlauf über `user_profiles.org_id` die
Organisation; die RLS-Policy `org_select_member` (0024) gibt genau die eigene heraus.

Die Abbildung der vier Stufen auf `free|pro` liegt in **`web/lib/stufeZuTier.js`** als reines
JS — Hausmuster `filterMarken.js`, damit `web/scripts/pruefe-stufe.mjs` die echte Funktion
fahren kann statt den Quelltext abzutasten. Das ist hier mehr als Formsache: `tier.ts`
*erwähnt* die alte Quelle `user_profiles.plan` in seinen Kommentaren, eine Regex darauf
schlägt an der Begründung an statt am Code.

Drei Dinge fallen fail-closed aus, jedes mit eigener Meldung statt stillem `free`:

| Fall | Verhalten |
|---|---|
| Spalte fehlt (`42703`, 0028 nicht eingespielt) | eigene FATAL-Meldung, nennt 0028 |
| `org_id` ist null | eigene Meldung, nennt `handle_new_user` (0024 Phase 2) |
| Organisation nicht lesbar (RLS) | eigene Meldung mit der org-ID |

⚠ Zum zweiten Fall: hier stand, `handle_new_user` sei nicht erweitert. Das war falsch —
0024 hatte es als Phase 2 ANGEKÜNDIGT, **0025 hat es ausgeführt** (Org, erstes Profil,
`role='owner'`). Gemessen am 2026-10-01: **0 von 13 Nutzern** ohne Organisation. Der Riegel
bleibt trotzdem sinnvoll, weil ein eingeladener Nutzer laut 0025 bewusst am Org-Zweig vorbei
angelegt wird. Die nächste
Selbstregistrierung erzeugt aber einen Straggler.

---

## 3. Die Obergrenze ist stufenabhängig (eingespielt)

v1.9: *„Auf Analyse und Strategie gibt es keine Obergrenze."* Heute setzt
`0025_active_profile_switch.sql` sie **unbedingt** durch:

```sql
-- heute, Zeile 78 f.
select profiles_paid into grenze from public.organizations where id = new.org_id;
if grenze is not null and n >= grenze then raise exception ...
```

Damit wechselt `profiles_paid` seine Rolle: **von Kontingent zu abgerechneter Menge.** Das
ist die eigentliche inhaltliche Änderung an v1.9, und sie ist grösser als sie aussieht —
eine Grenze, die nicht mehr greift, muss aus dem Trigger raus, sonst scheitert das Anlegen
des neunten Profils auf einer Stufe, die laut Preismodell unbegrenzt ist.

```sql
create or replace function public.pruefe_profil_grenze()
returns trigger language plpgsql as $$
declare n int; grenze int; t text;
begin
  select tier into t from public.organizations where id = new.org_id;
  -- ⛔ NUR Free und Testphase sind begrenzt (§7.3). Das ist eine STUFENgrenze,
  -- keine Abrechnungsgrenze: auf Analyse/Strategie wird die Menge gezaehlt und
  -- berechnet, nicht verweigert.
  if t not in ('free','trial') then
    return new;
  end if;
  select count(*) into n from public.profiles where org_id = new.org_id;
  if n >= 1 then
    raise exception 'Free und Testphase fuehren genau ein Unternehmensprofil (§7.3).'
      using errcode = 'check_violation';
  end if;
  return new;
end;
$$;
```

Für `pruefe_seat_grenze()` gilt dasselbe wortgleich mit `user_profiles`/`seats_paid`.

**Eingespielt als `0032`, am laufenden System geprüft** (eine Transaktion, danach
zurückgerollt, die 13 Organisationen blieben unberührt):

| Stufe | zweites Profil | zweite Einladung |
|---|---|---|
| `free` | gesperrt ✓ | gesperrt ✓ (Sitz vom Inhaber belegt) |
| `trial` | gesperrt ✓ | — |
| `analyse` | erlaubt ✓ | erlaubt ✓ |

⚠ Geprüft wird `tier in ('analyse','strategie')` und **nicht** `tier not in ('free','trial')`.
Fände die Abfrage keine Organisation, wäre `t` NULL, und `NULL not in (…)` ist NULL — der
Riegel wäre übersprungen und die Grenze griffe nicht. In der positiven Form ist NULL ebenfalls
nicht wahr, also ist jede unbekannte Stufe begrenzt statt frei.

Die Grenze für Free und Testphase ist fest **1** und nicht `profiles_paid`: das ist eine
Stufengrenze, und ein Free-Konto rechnet nichts ab, also darf eine Abrechnungsmenge dort auch
nichts erlauben. Festgehalten in `tests/test_stufengrenzen.py`.

> ⚠ **Was dadurch möglich wird und gewollt ist:** `count(profiles) > profiles_paid`. Genau
> dieser Zustand trägt die Proration — der Kunde legt ein Profil an, die Menge steigt, die
> Rechnung folgt unterjährig. Der Trigger darf das nicht verhindern, sonst gibt es keine
> Erweiterung, die man freigeben könnte. **`profiles_paid` ist ab hier eine
> Abrechnungsgrösse und keine Erlaubnis.** Die Kommentare in 0024 („erlaubte Profile")
> müssen mit.

---

## 4. Preise konfigurierbar, Mengenstaffel ohne Schemaänderung nachziehbar

v1.9 verlangt beides. Eine Tabelle mit **Mengenband im Schlüssel** erfüllt es: heute eine
Zeile je Position, später mehrere, ohne DDL.

```sql
create table if not exists public.preise (
  code        text not null,                -- 'analyse' | 'strategie' | 'erweiterung'
  ab_menge    int  not null default 0,      -- untere Bandgrenze, inklusive
  preis_monat numeric(10,2) not null check (preis_monat >= 0),
  preis_jahr  numeric(10,2) not null check (preis_jahr  >= 0),
  gilt_ab     date not null default current_date,
  gilt_bis    date,                         -- offen = aktuell gueltig
  primary key (code, ab_menge, gilt_ab)
);

comment on table public.preise is
  'Listenpreise. ab_menge traegt die Mengenstaffel: heute genau eine Zeile je code mit '
  'ab_menge=0. Eine Staffel entsteht durch WEITERE ZEILEN, nicht durch eine Schemaaenderung '
  '(§5.2 Preismodell). gilt_ab/gilt_bis halten alte Preise fuer Bestandskunden.';

insert into public.preise (code, ab_menge, preis_monat, preis_jahr) values
  ('analyse',     0,  99.00, 1019.00),
  ('strategie',   0, 349.00, 3579.00),
  ('erweiterung', 0,  29.00,  299.00)
on conflict do nothing;
```

Alle drei Jahrespreise sind gegen §5.1/§5.2 **und** gegen die Regel aus §13 (10,25 × Monat,
aufgerundet auf 9er-Endung) geprüft, beide Wege stimmen überein:

| Position | Monat | 10,25 × Monat | auf 9er | §5.1/§5.2 nennt |
|---|---:|---:|---:|---:|
| Analyse | 99 € | 1.014,75 € | 1.019 € | 1.019 € ✓ |
| Strategie | 349 € | 3.577,25 € | 3.579 € | 3.579 € ✓ |
| Erweiterung | 29 € | 297,25 € | 299 € | 299 € ✓ |

Die Erweiterungsmenge bleibt abgeleitet und wird nicht gespeichert:

```sql
create or replace view public.abrechnung_zeilen as
select o.id as org_id, o.tier, o.abo_status,
       greatest(o.seats_paid    - 1, 0) as erweiterung_nutzer,
       greatest(o.profiles_paid - 1, 0) as erweiterung_profile,
       greatest(o.seats_paid - 1, 0) + greatest(o.profiles_paid - 1, 0) as erweiterungen
from public.organizations o;

comment on view public.abrechnung_zeilen is
  'Erweiterungen = (seats_paid − 1) + (profiles_paid − 1), §5.2. Als Sicht und nicht als '
  'Spalte, damit die Zahl nicht gegen die Mengen driften kann. greatest(…,0) weil die '
  'erste Einheit im Paket enthalten ist.';
```

---

## 5. Was fehlt und nicht Teil von v1.9 ist

Zwei Lücken, die v1.9 nicht anspricht, die aber in §13 stehen und die Abrechnung berühren:

**`vorgang_credits` existiert nicht.** §4.3 definiert ein Zählwerk (Konto, Monat, Verbrauch)
plus `unlocked_leads` dauerhaft. In der Datenbank steht davon nichts. Ohne das greift das
Free-Kontingent von drei Vorgängen nirgends.

**`user_profile_assignments` existiert nicht.** §7.1 will „je Nutzer einem oder mehreren
Profilen zugeordnet"; `user_profiles.active_profile_id` kann genau eins. Das ist eine
ungebaute Anforderung aus §7, nicht ein Fehler — aber eine Organisation mit acht Profilen und
drei Nutzern lässt sich damit heute nicht einrichten, wie §7 es verlangt.

Beides ist eigener Umfang. Ich habe es nicht angefasst.

---

## 6. Reihenfolge

1. Die bezahlten Bestandskonten durchgehen und je Konto `analyse` oder `strategie` festlegen (§2).
2. Klären, ob `tier` an der Organisation allein hängt, und `getTier()` darauf umstellen (§2 Ende).
3. Dann Migration 0028 aus diesem Entwurf, additiv, `plan` bleibt stehen.
4. Erst danach Abrechnungslogik.

Punkt 1 und 2 sind beides Entscheidungen, keine Bauaufgaben. Punkt 2 ist der schwerere: solange
`tier` an zwei Stellen stehen kann, ist jede Abrechnungslogik darauf gebaut, dass die beiden
nicht auseinanderlaufen — und sie laufen auseinander, sobald jemand im internen Kontenwerkzeug
die eine Spalte setzt und das Gating die andere liest.

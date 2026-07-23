# Volltextsuche über Leads

> **Stand 2026-07-23: die Entwicklung läuft lokal.** Supabase ist Deploy-Ziel, nicht
> Arbeitsumgebung — solange das Produkt nicht steht, lohnt kein bezahlter Plan. Für die
> lokale Arbeit gilt **`govisor/search.py`** (DuckDB, `ILIKE`, kein Index, ~320 ms und
> vollständige Teilstring-Semantik). Alles unterhalb beschreibt die **Supabase-Variante**
> für den Tag des Deployments; sie ist gebaut und funktioniert, aber der Free-Tier ist
> mit 453/500 MB ausgereizt — s. „Platzbilanz" am Ende.

## Warum

Ein Lead war bisher nur über **Titel** und **CPV** auffindbar. Das ist zu grob: CPV ist eine
Behörden-Taxonomie, kein Vokabular, in dem ein Handwerker denkt. Gemessen 2026-07-23, wie
viele Leads ein Suchbegriff findet — je nachdem, wie weit man schaut:

| Suchwort | nur Titel | + Beschreibung | + Lostexte | Faktor |
|---|---:|---:|---:|---:|
| Wärmepumpe | 35 | 331 | **699** | 20,0× |
| Glasfaser | 23 | 116 | **258** | 11,2× |
| Photovoltaik | 91 | 325 | **628** | 6,9× |
| Brandmeldeanlage | 111 | 255 | **571** | 5,1× |
| Kanalsanierung | 37 | 73 | **87** | 2,4× |
| Schulmöbel | 39 | 45 | **47** | 1,2× |

Die Spreizung ist der eigentliche Befund: bei Leistungen mit eindeutigem Titel (Schulmöbel)
bringt die Tiefensuche fast nichts, bei **Komponenten, die als Teilleistung auftauchen**
(Wärmepumpe in einer Heizungssanierung) ist sie der Unterschied zwischen 35 und 699 Leads.

## Wie es gebaut ist

`gov_leads.search_doc` (`tsvector`, deutsche Wortstammerkennung) + GIN-Index über
`title` + `description` + alle `lot_title` + alle `lot_description` des Leads.

Drei bewusste Entscheidungen:

- **Keine `GENERATED ALWAYS`-Spalte.** Das Dokument zieht Text aus **zwei** Tabellen; eine
  generierte Spalte darf in Postgres nur auf die eigene Zeile zugreifen. Deshalb ein
  expliziter Refresh — `scripts/export_supabase.py` ruft ihn nach jedem Push automatisch,
  `scripts/build_search_index.py` macht es einzeln.
- **`strip()`** wirft die Positions-Information weg. Gemessen: 64 MB statt ~120 MB. Bei
  500 MB Free-Tier ist das der Unterschied zwischen „passt" und „passt nicht".
- **Kein `setweight`.** `strip()` entfernt Positionen **und Gewichte** — Gewichte werden
  pro Position gespeichert. Ein `setweight` vor dem `strip` sieht nach Feld-Ranking aus,
  ist aber wirkungslos (die erste Fassung hatte genau diesen Fehler: A/B/C gesetzt, und
  `search_doc::text ~ ':[ABC]'` war danach `false`). Feld-Ranking macht deshalb die
  Abfrage (s. „Ranking" weiter unten).

## Abfrage aus dem Frontend

**Immer mit Präfix-Operator `:*` suchen.** Deutsch ist eine Kompositasprache und der
Postgres-Stemmer zerlegt Komposita **nicht** — „Photovoltaikanlage" ist ein einziges Lexem
und wird von der Suche nach „Photovoltaik" ohne `:*` nicht gefunden. Gemessen 2026-07-23:

| Suchwort | exakt | **mit `:*`** | `ILIKE '%…%'` |
|---|---:|---:|---:|
| glasfaser | 76 | **359** | 116 |
| photovoltaik | 259 | **625** | 325 |
| aufzug | 1.262 | **1.938** | 1.172 |
| wärmepumpe | 521 | **605** | 331 |

Präfix schlägt Teilstring-Suche in **jedem** gemessenen Fall — und läuft über den GIN-Index
(~150 ms inkl. Ranking) statt als Full Scan. Zum Vergleich: dasselbe `ILIKE` über
`gov_leads` **und** `gov_lead_lots` lief in den 2-Minuten-Timeout.

```
GET /rest/v1/gov_leads?search_doc=fts(german).photovoltaik:*&phase=eq.open&select=slug,title
```

`fts` = `to_tsquery` (nimmt `:*`), `wfts` = `websearch_to_tsquery` (nimmt Nutzer-Syntax wie
`or` und `-ausschluss`, aber **kein** `:*`). Für eine Suchleiste: Nutzereingabe in Tokens
zerlegen und jedes mit `:*` versehen.

### Was auch mit `:*` nicht gefunden wird

Komposita, bei denen das Suchwort **hinten** steht — „Groß**wärmepumpe**" bei der Suche
nach „Wärmepumpe". Das bräuchte einen Trigram-Index (`pg_trgm`), der grob 80–100 MB
kostet; dafür ist im 500-MB-Free-Tier kein Platz. Auf einem grösseren Plan ist es ein
Einzeiler:

```sql
create index gov_leads_trgm_idx on gov_leads using gin (title gin_trgm_ops);
```

### Ranking

```sql
select slug, title
  from gov_leads
 where search_doc @@ to_tsquery('german', 'photovoltaik:*')
 order by (title ilike '%photovoltaik%') desc,           -- Titeltreffer zuerst
          ts_rank(search_doc, to_tsquery('german','photovoltaik:*')) desc;
```

Das `ilike` läuft nur auf der bereits gefilterten Treffermenge, kostet also nichts.

## Betrieb

```bash
python3 scripts/build_search_index.py --verify
```

zeigt Abdeckung und Grössen. `--drop` entfernt Spalte und Index wieder, falls der Free-Tier
eng wird. Nach jedem `export_supabase.py`-Lauf ist der Index aktuell; wer nur
`gov_lead_lots` ändert und den Refresh überspringt (`--no-search-index`), sucht auf einem
veralteten Stand.

## Platzbilanz (Free-Tier)

Gemessen nach dem Einbau:

| Posten | Grösse |
|---|---:|
| `search_doc` (tsvector, gestrippt) | 64 MB |
| `gov_leads_search_idx` (GIN) | 41 MB |
| **Datenbank gesamt** | **453 MB von 500 MB** |

Das ist **eng**. Der Suchindex ist nicht der Hauptposten — die Volltexte selbst sind es
(`description` 31 MB, `lot_description` ~90 MB). Und der Bestand wächst monatlich.

Der Free-Tier ist damit ausgereizt. Optionen, ehrlich sortiert:

1. **Supabase Pro** (~25 $/Monat, 8 GB) — löst das Problem, macht zusätzlich den
   Trigram-Index möglich und ist gegenüber dem Preismodell der Plattform vernachlässigbar.
2. **Text kürzen** — `options_description` + `renewal_description` streichen (17 MB),
   `lot_description` deckeln. Spart wenig und kostet genau die Inhaltstiefe, für die die
   Los-Tabelle gebaut wurde.
3. **Volltexte auslagern** (Storage/eigener Dienst) und in Postgres nur `search_doc` +
   Metadaten halten. Technisch sauber, aber deutlich mehr Bewegtteile.

`python3 scripts/build_search_index.py --drop` entfernt Spalte und Index wieder, falls es
kurzfristig eng wird.

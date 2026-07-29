# goVisor — Projektkontext für Claude

Analyse-Engine über TED-Vergabedaten (öffentliche EU-Ausschreibungen) als Grundlage
für Wechsel-Prognosen und Lead-Generierung. Nutzer: Sven (sven.kotzur@gmail.com).

## Wo das Wissen liegt (zuerst lesen)
- `docs/entscheidungen-und-kontext.md` — Nicht-Code-Wissen: Architektur-Entscheidungen,
  Firmengruppen-Logik, **Arbeitsweise**, **Preismodell**, offene Punkte.
- `docs/concept-v3.md` — Gesamtkonzept der Engine.
- `docs/data-sources.md` — gemessene TED-Datenrealitäten (Abdeckung, Fallstricke).
- `docs/field-categories.md` — Feldkategorisierung.
- `docs/mehrwert-roadmap.md` — priorisierte KPI-/Feature-/Externe-Quellen-Landkarte (mit gemessenem
  Mehrwert, für Versionszuordnung).
- Auto-Memory (`MEMORY.md` + `govisor-*.md`) ist zusätzlich hinterlegt.
- **Secrets:** OpenRouter-API-Key (LLM-Nachfolge-Adjudikation) liegt in
  `.secrets/openrouter.key` (gitignored, chmod 600). ~$25 Startguthaben; Fallback-Key
  von Sven, wenn aufgebraucht. Nutzung: `OPENROUTER_KEY_FILE=.secrets/openrouter.key`.

## Architektur (Kurzform)
Medallion: **Bronze** (Original-TED-XML, verlustfreie Quelle, nach Land gefiltert) →
**Silber** (normalisierte Parquet-Tabellen, kein JSON) → **Gold** (abgeleitet/kuratiert).
Lokal DuckDB/Parquet. Quelle sind die monatlichen XML-Bulk-Pakete, NICHT der CSV-Export.
Bestand: DE komplett, alle CPV, **2004-01–2026-06 (270 Monate, lückenlos), 1.832.998
Notices, 0 Dubletten**, gegen TED-API verifiziert. Vier Schema-Generationen im Parser
(`schema_gen`): `legacy` (TED_EXPORT, 1,15 Mio), `eforms` (0,43 Mio), `text` (Vor-XML-
Textformat, 0,25 Mio, cp1252-Fallback), `ojs` (INTERNAL_OJS, OPOCE-Altformat, u. a. 2008-05).
CLI: `python -m govisor.cli {ingest|silver|gold|verify|review}`.

## Arbeitsweise (wichtig, von Sven eingefordert)
- **Messen statt annehmen** — jede Zahl/Feldposition an echten Daten prüfen, nie aus
  dem Gedächtnis behaupten. Auffällige Aggregat-Zahlen sind Warnsignale.
- **Kein Datenverlust** — nichts nach eigener Relevanz filtern; Unbekanntes →
  „sonstiges"/`attributes`, Zweifelsfälle → `review`-Queue. Erschlossenes trägt Konfidenz.
- Details + Warum: `docs/entscheidungen-und-kontext.md`.

## Aktueller Stand (2026-07-19)
- **Backfill 2004–2015 + Qualitäts-Reparatur fertig** (`REPAIR2_DONE`, Audit-Trail
  `data/repair.log` + `data/repair2.log`, Skripte in `scripts/`). Bestand jetzt **1.832.998
  DE-Notices, 2004-01–2026-06 lückenlos (270 Monate)**. Drei Root-Causes des Nacht-Ingests
  behoben: (1) **Doppel-Ingest 2004–2009** (ISO+UTF-8-Zwillinge) → Silber-Dedup neu gebaut,
  ~112k Dubletten weg; (2) **2004 nur-ISO-Encoding** → neuer `flatten.decode_text()` mit
  cp1252-Fallback, 11.448 Notices verlustfrei recovered, ~115k `�`-Zeilen weg; (3) **2008-05
  fehlte** — TED liefert den Monat nur im Legacy-Format INTERNAL_OJS → dedizierter Parser
  `schema._parse_internal_ojs` (`schema_gen='ojs'`), 3.232 DE-Notices mit 100 % Titel/CPV/
  Käufer, Gewinner+Werte für Awards. Verifiziert: 0 Dubletten, 0 Encoding-Schäden (2 echte
  Quell-`�` bleiben bewusst), 0 Gold-FK-Waisen. 75 Tests grün.
- **final5-Rebuild** (Vorstufe, Silber `--force` → Gold → Verify, `FINAL5_DONE`). War 1,316,049
  DE-Notices (nur 2016–2026), 9 Gold-Tabellen — durch den Backfill oben abgelöst.

### Entity-Härtung + Analytik-Layer (2026-07-19, Fortsetzung)
- **Entity-Resolution Stufe 1** (`gold._consolidate_by_national_id`): nur-Name-Entitäten in ihre
  belegte Register-/ID-Entität verschmolzen — **nur bei geteilter PLZ** (0 Fehl-Merges), sonst
  geflaggt in `entity_merge_candidates.parquet`. −6.279 Dubletten, national_id-Quote 31,9→32,5 %.
- **Stufe 2 (Fuzzy-HR) VERWORFEN & gegated.** Gemessen: Schwelle 0.7 → ~24 % Fehl-Merges bei
  winzigem Ertrag (1.428). `build_hr_index(fuzzy=False)` per **Default** (Blocking wird nicht
  gebaut → Exakt-Match-Verhalten). Code bleibt für spätere Verschärfung. **Erkenntnis: Entity-
  Resolution über Namen ist ausgereizt** — mehr ginge nur über externe Register.
- **🟢 Markt-Intelligenz-Views** (`gold.build_market_intelligence`, 5-J-Fenster): `buyer_stats`
  (23.998), `contractor_stats` (170.947, Rang/Anteil nach Win-Zahl), `market_stats` (10.642),
  `buyer_contractor_history` (266.448). Nur nachfolge-freie KPIs; Volumen/Laufzeit tragen
  `*_coverage` (Volumen 55,8 % unbekannt).
- **Nachfolge-Modell** (`gold.build_content_successions`) — **löst die kaputte `contract_chains`
  für KPIs ab.** Gestufter Trichter: (A) Behörde+CPV+Zeit, NUR ketten-würdig (`_kind_sql`, kein
  nicht-Rahmen-Bau), (B) Titel-Token-Score + CPV-Bonus + Laufzeit-Timing + Same-Verfahren-Ausschluss.
  → **63.770 konfidente Kanten** (content_unique) + **36.301 LLM-adjudiziert** = **100.071
  verifizierte Nachfolgen** in `contract_succession.parquet`. LLM-Stufe (`scripts/succession_llm.py`,
  OpenRouter `gemini-2.5-flash-lite`, Voll-Lauf über 105k = **$2.01**, 35 % bestätigt) via
  `gold.merge_llm_successions`. Von **7 % Artefakt** auf ~24 % ketten-würdige Abdeckung.
- **🔴 Nachfolge-KPIs** (`gold.build_succession_kpis`): `succession_events` (51.027), `head_to_head`
  (20.150), `market_switch_rate`, `buyer_loyalty`, `contractor_loss`. Gewinner-Matching
  **gruppen-bewusst + Multi-Gewinner-Set-Schnitt + Konsortien geflaggt** (beim Messen als
  entscheidend erkannt: naiv 1-Gewinner ergäbe irreführende 78 % Verdrängung durch Siemens-
  AG↔Mobility-Fragmentierung/ARGE). **Incumbent-Retention 28,3 %** auf den 100k verifizierten
  Nachfolgen (belastbar, vs 7 % Artefakt). `succession_events` 80.638, `head_to_head` 31.364.
  Alle neuen Tabellen in `verify.gold_integrity` (FK sauber). 84 Tests grün.

### Weitere Grundlagen (2026-07-19, Forts.)
- **`avg_decision_days`** in `buyer_stats` (cn→can via `ref_publication_number`, ~42 % Coverage,
  Guard ≥3 Belege, Median ~87d) — schließt #4-D2.
- **`incumbent_tenure`** (`gold.build_incumbent_tenure`): „seit wann Incumbent" aus den Nachfolge-
  Ketten — 22.742 Incumbents mit Historie (längste Kette 9 Zyklen). Schließt #3/#4-D4.
- **`build_prospective_leads`**: F01/F02 (`cn`/`pin`) mit **zukünftiger Angebotsfrist** als Lead-
  Zeilen ins `leads`-Parquet (neue Spalte `source ∈ {auslauf,f01,f02}`). Awarded-only-Felder
  (Incumbent, Wechsel-Score, num_tenders) NULL via `UNION ALL BY NAME`. Aktuell **4.754** prospektive
  Leads (stichtag-abhängig). Speist #1 Master-Liste (vorher nur Auslauf-Radar).
- **CPV-Fund:** Mehr-CPV liegt bereits typisiert in `silver/notice_cpv` (3,5 M, Ø 1,92/Notice) →
  Anforderungs-Match (#3/#4) sofort per join `notice_id`.
- **`dim_cpv_label`** (`gold.build_dim_cpv_label`): volles CPV-Code→DE-Label-Vokabular (9.454 Codes)
  aus der offiziellen EU-CPV-2008-Liste (`data/reference/cpv_2008.xml`, Download-URL im Docstring).
  Nutzungsgewichtete Coverage **97 % (100 % ab 2016**; Rest = Legacy-CPV-2003 in Alt-Jahren).
  `dim_cpv` (45 Divisionen + Branche) bleibt als grobe Ebene.
- **Buyer-Aliase (E, kuratiert):** `gold._load_entity_aliases` + `data/curated/DE_entity_aliases.csv`
  — belegte Umbenennungen/Fragmente als **Identitäts**-Merge in `build_entities` (analog Stufe 1,
  aber human-verifiziert; KEIN Namensstamm-Automatismus). Seed: **DB Netz↔DB InfraGO** (Umbenennung
  2024, gleiche HRB50879) → DB Netz konsolidiert 15.662→**22.104** Vergaben (7 InfraGO-Fragmente).
  **Bewusst NICHT gelöst:** öffentliche-Stellen-Fragmentierung (61 % der Vergaben, nicht im HR,
  Vertretungs-/Abteilungs-Zusätze) — nicht sicher automatisierbar, bleibt gezielter CSV-Kuratierung.
- **ARGE-Zerlegung (G): studiert, NICHT gebaut.** Machbarkeitsstudie (gemessen): Konsortial-Namen
  sind regelbasiert zu 26 % in ≥2 Mitglieder zerlegbar (90 % COMPANY, 42 % Register-Match), ABER der
  Nutzen ist winzig — nur **479 (0,6 %) aller Nachfolgen** würden von „unbestimmbar" auf „Retention"
  kippen. **Die ARGE-Fluktuation ist überwiegend echt** (je Projekt andere Bietergemeinschaft), kein
  Artefakt. Die 11 % Konsortial-Nachfolgen bleiben ehrlich „unbestimmbar". (Offener Winkel für später:
  Mitglieder-Aktivität für `contractor_stats` — eigenes Feature, kein Grundlagen-Blocker.)
- **Granularer Qualitäts-Audit + neue Signale:** neue Quality-Flags `wert_sentinel` (100k
  0,01/1,00-Platzhalter), `frist_vor_pub` (271), `datum_absurd` (44, →Review-Queue),
  `waehrung_angenommen` (61k, informativ). **Neu `verfahren_status`** in `quality` (kein Defekt,
  sondern Lead-Signal): `erfolglos` **93.911** CANs ohne Gewinner+Award = „2.-Versuch"-Radar-Basis
  (52 % re-tendered). A6-Guard in `build_prospective_leads` (Frist ≤ +5 J). Offen als Feature:
  Re-Tender-/Contestedness-KPI (Roadmap T1.1/T1.2).
- **A2-Parser-Lücke untersucht & aufgelöst:** die 27k „unbekannt"-CANs (Award, kein Gewinnername) sind
  zu **>99 % KEIN Bug** — der Gewinner steht schlicht nicht im XML (legacy 0 % rückholbar; eForms 71 %
  echt nicht-vergeben). **Real rückholbar: ~200 eForms**, die den Gewinner nur als `SettledContract.
  SignatoryParty` (≠ Käufer, ohne Vergabekammer/eSender) tragen. Fix: SignatoryParty-Fallback in
  `schema._parse_eforms` (verifiziert an „Bellersheim Abfallwirtschaft GmbH", Test grün). Kein
  dedizierter Rebuild für ~200 Sätze — greift beim nächsten regulären Gold-/Silber-Rebuild. Die
  restlichen 27k `unbekannt` sind korrekt (kein `erfolglos`) → verunreinigen keine KPI.
- **⭐ `market_opportunity` (Flaggschiff-Datenprodukt, `gold.build_market_opportunity`):** Marktchancen-
  Landkarte je CPV-Segment (5-J), 511 Segmente. Achsen: Nachfrage × Schwäche (erfolglos+single-bidder,
  A2-Kern) × Wert, plus **Struktur** (top3_share → fragmentiert/moderat/oligopol) und **Top-Dominatoren
  = Buy/Partner-Kandidaten**. `opportunity_score` (Perzentil-Ranking). Basis für den White-Space-Explorer
  (Make/Buy/Partner). 3-J-Fenster (aktuelle Chance), `window_start/end` + `last_award_year` transparent.
  Validiert: reale Hochwert-Segmente mit 30–90 % Single-Bidder/erfolglos.
- **⭐ `retender_signal` (`gold.build_retender_signal`):** chronische Fehl-Ausschreibungen — „seit X Jahren
  Y-mal erfolglos gesucht". **Inhaltsgeclustert** (Titel-Token wie Nachfolge-Modell; naiv überzählt bei
  Framework-Losen — DAK-Arzneimittel 440× war Open-House, nicht 440 Suchen). Zählt distinkte Fehl-JAHRE,
  282 aktuell relevante chronische Bedarfe (z.B. Trier Schulzentrum 4× über 4 J). Aggregiert als
  `chronic_needs` in `market_opportunity`. Der stärkste Kauf-/Chancen-Hinweis. **Open-House-Rabatt-
  verträge (§130a) als eigener `verfahren_status='open_house'`** abgetrennt (kein Wettbewerb, kein
  Fehlsignal).
- **⭐ `cpv_adjacency` (`gold.build_cpv_adjacency`):** CPV-Segment-Nähe über Firmen-Co-Occurrence
  (`cond_prob` = P(Firma bedient B | bedient A)). 37.920 Kanten. Die „Nähe"-Achse des Radars → macht
  Chancen persönlich („offene Märkte nah an deinem Skill"). Validiert: Datenbankdienste → IT/Software.
- **`value_band_effektiv` (`gold.build_value_band_effektiv`):** Gebühren-Basis je Lead — nie „unbekannt":
  echter Wert (37 %) / geschätzt (5 %) / CPV-Median-imputiert (52 %) / default (6 %), mit `band_source` als
  Fairness-Regler. Basis `value_real_2020`. **7-Band-Pricing-Schema** (`_band_sql`, Grenzen 100k/250k/500k/
  1,3M/5M/25M, an den Wert-Perzentilen) — bewusst getrennt vom KPI-`value_band` (5 Bänder). Default-Band
  `250-500k`.
- **`govisor/pricing.py`:** gebaute Staffel — **reines Flat-per-Band** (7 Stufen, Pauschalen verdoppeln
  sich: `<100k`=600 / `100-250k`=1.200 / `250-500k`=2.400 / `500k-1,3M`=4.800 / `1,3-5M`=9.600 /
  `5-25M`=15.000 / `>25M`=25.000 €). `imputiert`/`default` → ×0,8. `SCHEDULE` + `fee(band,source,value)`;
  Keys = exakt `_band_sql`-Labels. `python -m govisor.pricing` → Verteilung an 75.014 Leads (Ø ~3.210 €/Lead;
  Summe ~241 Mio. € = Obergrenze bei 100 % Gewinn). **Warum Flat statt %:** Wert-Schätzung trifft nur ~42 %
  das richtige Band (gemessen) → % auf geratenen Wert nicht verteidigbar; abrechnen auf echtem Wert (65 %),
  Rest via Kunden-Bestätigung. Mechanik: [`docs/pricing-modell.md`]; Marktvalidierung: [[govisor-pricing-research]].
  **Offen (Business):** finale Beträge, Rabatt-Faktor, Attributions-/Rechnungs-Mechanik (s. Ticket-06-v2).
- **`award_tender_link` (`gold.build_award_tender_link`):** Zuschlag↔Ausschreibung via `ref_publication_number`
  (373k Links, 0 Dup je Award, gap-Median 114 T). Fundament für Attribution (#6) + Award-Alerts (#9). FK-geprüft.
- **`value_anchor` (`gold.build_value_anchor`):** Wert-**Wächter** je Zuschlag fürs Billing (#6) — Waterfall
  Ausschreibungssumme→Vorgänger→Buyer×CPV→Buyer→CPV, **nominal**. Kein Orakel (Schätzung ~42 % exakt), sondern
  Lowball-Plausibilitätscheck (~68 % ±1) gegen Kunden-Selbstauskunft. 98 % Abdeckung (96 % im wertlosen Drittel).
  `anchor_band`-Labels = `pricing.SCHEDULE`-Keys. **Billing-Regel:** echt=Fakt, sonst Kunde bestätigt + Anker-Flag
  bei ≥2 Bänder-Abweichung → HITL. Roadmap/Reifegrad: [`docs/v1-gap-analysis.md`].
- **`lead_deadline` (`gold.build_lead_deadline`):** Angebotsfrist je offener Ausschreibung (`cn`/`pin`) — der
  **primäre Timing-Alert** (#9-Flip). 861k Zeilen, **0 NULL** (63 % echt `submission_deadline`, Rest geschätzt aus
  CPV-Median-Bid-Fenster/global ~31 T, gesetzl. mindestgeregelt → belastbar). `deadline_source` flaggt Herkunft.
  **Wichtig:** echte Frist braucht KEIN `publication_date` (nur die Schätzung) — sonst fielen die aktuellsten
  offenen Ausschreibungen (echtes Datum, oft ohne pub) raus. Deckt jetzt 4.418/4.418 prospektive Leads.
- **`lead_duration` (`gold.build_lead_duration`):** Vertragsende je Lead (`can`/`cn`) für „bis Auslauf" (#3) +
  sekundären Auslauf-Alert. Waterfall echt→`start_date`+CPV-Median→`award_date`+CPV-Median→unbekannt; **66,8 %**
  mit Ende (33 % echt), Rest ehrlich `unbekannt` (kein erfundenes Datum). `duration_source` geflaggt.
- **`lead_detail` (`gold.build_lead_detail`):** UI-View je Lead (1:1 zu `leads`) — führt die ehrlichen Flags
  zusammen: `band_effektiv`/`band_source`, `contract_end_eff`/`duration_source`, `deadline_date`/`deadline_source`,
  Incumbent-Tenure. Das Frontend (#3) bekommt alle Herkunfts-Kennzeichnungen an einer Stelle. FK-geprüft.
- **`entity_identity` (`gold.build_entity_identity`):** „Gruppe = Identität"-Auflösung (P0-3) — jede Entity →
  stabile `identity_id` (Gruppen-ID oder `solo:<id>`). Fundament für **Winner-Matching** (#6/#9: Gewinner → alle
  Schwester-Entities) + Onboarding (#7). 323k Entities → 302k Identitäten. **Matching-Regel:** Gewinner und
  bestätigte User-Identität teilen dieselbe `identity_id`.
- **`dim_plz` (`gold.build_dim_plz`) + `lead_geo` (`gold.build_lead_geo`) + `govisor/geo.py`:** **Radius-Suche**
  (Stadt + Umkreis). `dim_plz` = PLZ→Zentroid aus GeoNames (`data/reference/geonames/DE.txt`, 10.813 PLZ);
  `lead_geo` = Koordinate je Lead (Buyer-PLZ→dim_plz, sonst Ort-Fallback; `geo_source`-Flag; **99,8 % Abdeckung**);
  `geo.geocode_city`/`radius_search`/`radius_count` = Haversine-Distanzfilter. Bsp. München: 5/10/25/50/100 km →
  3.376/4.076/4.561/4.999/6.616 Leads. **`geo.search(...)` kombiniert Radius UND NUTS-Filter** (`lead_geo.nuts` =
  buyer_nuts, 99,8 % NUTS-3; Präfix-Match, injection-validiert). **`dim_nuts`** (`gold.build_dim_nuts`, aus
  EU-GISCO `NUTS_AT_{2021,2024}.csv`, 462 Codes) + `geo.nuts_autocomplete`/`nuts_children` = Regions-
  Namens-Autocomplete + Drill-down mit Lead-Zahlen. **Zwei Achsen** (`geo.search(axis=...)`): `buyer`
  (Auftraggeber, feine PLZ) vs. `performance` (Leistungsort, `perf_nuts` + NUTS-3-Zentroid, grob) —
  1.579 Leads mit Buyer-NUTS≠Perf-NUTS. Details/Caveats: [`docs/radius-suche.md`].
- **App:** `app/radius_suche.py` (Streamlit, `streamlit run`) — Umkreis- & Regionssuche zum Durchklicken:
  Stadt+Radius (5–100 km), Region-**Namens-Autocomplete** (via `geo.nuts_autocomplete`), Achsen-Toggle
  (Auftraggeber/Leistungsort), interaktive Karte + Ergebnistabelle. Verifiziert: 25 km München = 4.561,
  ∩ Oberbayern = 4.527.
- **App:** `app/marktchancen.py` (Streamlit) — Marktchancen-Radar zum Durchklicken + **Sidebar-Regional-Filter**
  (Achse Leistungsort/Auftraggeber, Region-Namens-Autocomplete via `geo`, Umkreis) auf die Segment-Aufträge:
  Segment-Chancen
  (Score/Struktur/Buy-Longlist/konkrete Aufträge), Verzweiflungs-Chronik, **„Für dich"** (Footprint →
  Fit = Chance × Nähe). Start: `streamlit run app/marktchancen.py`.
- **Feature-Checks gelaufen** (`scripts/feature_checks.py`): IT-Lose & Konsortialquote sauber.
  **Historische Erkenntnis (jetzt adressiert):** Incumbent-Rate 7 % war ein Paarungs-Artefakt der
  `contract_chains` (paart bei Großkäufern unabhängige Verträge) — ersetzt durch das inhaltsbasierte
  Nachfolge-Modell oben (Retention 32,5 %). Details: `docs/plan-radar-und-score.md` (Gate-Abschnitt).
- **#1 Auslauf-Radar gebaut** → `data/gold/DE/leads.parquet` (70.246 Leads, `gold.build_leads`).
- **#2 Verdrängbarkeits-Score gebaut** → `dim_displaceability.parquet` + Score-Spalten auf
  `leads` (`gold.build_displaceability`). Framing: *Verdrängbarkeit* (relatives Ranking nach
  Bieterzahl × Branche), NICHT „Amtsinhaber gewinnt wieder".
- **#3 lokales Dashboard gebaut** → `app/dashboard.py` (Streamlit auf `leads.parquet`).
  Start: `streamlit run app/dashboard.py`. Spalten nach goVisor-X-RAY (Status/Auftraggeber/
  Auftragsgegenstand/Dienstleister/Volumen/Vergabe/Fällig/Fällig-Basis/TED) + Score-Spalten.
  Filter (Branche/Auslauf/Wert/Verdrängbarkeit/Konfidenz), sortierbar (Default: nächste
  Ausschreibung), Lead-Detail+Kontakt, Modell- + Review-Queue-Expander.
- **Datenqualität — Fehler markieren statt wegwerfen (Prinzip, nicht droppen):** `quality`
  flaggt jetzt umfassend (laufzeit_unplausibel, bieterzahl_unplausibel, waehrung_fremd,
  datum_start_nach_ende, schaetzwert_negativ, wert_verdaechtig/absurd …). `final_value_clean`
  nur bei plausibel UND EUR. `gold.build_review_queue` → `review_queue.parquet` = ~7.457 harte
  Fehler als Worklist mit Beleg-Link. `build_leads` droppt NICHTS, trägt `termin_plausibel`
  + Lead-Dedup (`ist_hauptlos`/`lose_im_cluster`). Voller Audit: `docs/db-audit-und-haertung.md`.
- **Offene Kern-Schwäche: Entity-Resolution** (36 % nur-Name, Ø-Konfidenz 0,47, Fragmentierung)
  — eigenes Härtungsprojekt, Plan in `docs/db-audit-und-haertung.md`.
- Weitere offene Punkte: `docs/entscheidungen-und-kontext.md` (ARGE-Namen zerlegen,
  Rahmenvertrags-Abrufe, LLM-Schritte, externe Quellen).

## Arbeitsweise: lokal entwickeln, Supabase ist Deploy-Ziel (Stand 2026-07-23)

**Entscheidung von Sven:** kein bezahlter Plan, solange das Produkt nicht steht — der Weg
ist noch lang. Alles wird **lokal** auf Parquet/DuckDB gebaut und geprüft; Supabase (und
später Vercel) bekommen den fertigen Stand. GitHub läuft normal weiter.

Konsequenzen fürs Bauen:
- **Suche lokal = `govisor/search.py`** (DuckDB `ILIKE` über `title`/`description`/
  `lot_title`/`lot_description`, ~320 ms, kein Index). Sie ist der Postgres-Volltextsuche
  in der Trefferqualität **überlegen**: volle Teilstring-Semantik findet „Großwärmepumpe",
  was der deutsche Stemmer in Postgres selbst mit `:*` nicht kann. Wer Trefferzahlen
  zwischen beiden vergleicht, vergleicht **Verfahren, nicht Datenstände**.
- **Der Export-Pfad bleibt einsatzbereit**, wird aber nicht mehr routinemässig gefahren:
  `python3 scripts/export_supabase.py --prune` + `scripts/build_search_index.py`.
- **⚠️ In Supabase liegt seit 2026-07-23 nur ein ENTWICKLUNGS-SAMPLE** (~2.048 Leads +
  zugehörige Lose/CPV), **nicht** der Bestand. Wer dort zählt, zählt das Sample — jede
  Kennzahl kommt aus dem lokalen Parquet. Neu ziehen:
  `python3 scripts/supabase_dev_sample.py [--size N] [--dry-run]`. Das Sample ist
  **geschichtet** (Phase × Quelle × Beschreibungstiefe × Mehrlosigkeit) plus erzwungene
  Extremfälle (267-Lose-Ausschreibung, fehlender Wert, fehlende Region, unplausibles
  Timing) — ein Zufallssample träfe fast nur den Regelfall und das Frontend bräche später
  an jeder Abweichung.
- **Der Free-Tier war mit dem Volldatensatz ausgereizt** (453/500 MB, s.
  `docs/volltextsuche.md`). Vor einem erneuten Voll-Push braucht es einen grösseren Plan
  oder eine Textreduktion — nicht einfach nochmal draufschieben.

## Frontend-Layer: Supabase — gebaut, ruht bis zum Deployment (Stand 2026-07-23)

Projekt `production` in der Org **goVisor** (`tegznbkbvbbbgzhsvoza`). Creds in `.secrets/`
(`supabase.txt` = URL **+** Secret-Key in **zwei Zeilen**, `supabase_db.txt` = DB-Passwort).
`psql` verbindet von dieser Maschine aus **direkt** (`db.<ref>.supabase.co:5432`) — DDL geht
also ohne Dashboard. (Das gilt nur für dieses Projekt; beim geteilten `ouzapbkguhlrbmovydmz`
scheitert der Pooler, s. Auto-Memory.)

- **`scripts/export_supabase.py`** — eine Registry `TABLES` steuert alles: `gov_leads`
  (PK `lead_id`), `gov_lead_cpv` (PK `lead_id,cpv_code`), `gov_lead_lots` (PK
  `lead_id,lot_id`). DDL wird **aus dem Parquet-Schema generiert** und enthält neben
  `create table if not exists` auch je Spalte ein `alter table … add column if not exists`
  — dieselbe Datei legt an *und* migriert, mehrfach ausführbar. Ohne diesen Teil wäre eine
  neue Spalte am `create if not exists` lautlos abgeprallt (Upsert → PGRST204).
  `python3 scripts/export_supabase.py [--table all|<name>] [--dry-run]`.
- **Vertrag ist durchgehend ENGLISCH** — Spalten *und* Werte (`phase`=expiring/open/planned,
  `*_source`=actual/estimated/uncertain/unknown, Bänder=high/medium/low/na). Das Vokabular
  ist in `tests/test_plumbing.py::_EXPORT_VOCAB` festgenagelt.
- **RLS auf allen Tabellen**: nur `authenticated` liest → Registrierung schaltet Leads frei.
  Analyse-Tabellen bekommen bewusst **keine** Policy (Paywall). Der Secret-Key umgeht RLS und
  gehört ausschliesslich serverseitig — nie ins Frontend-Bundle.
- **Inhalts-Layer `gov_lead_lots`** (`gold.build_lead_lot`): das Los ist die Entscheidungs-
  Einheit (man bietet auf ein Los, nicht auf die Bekanntmachung) und trägt **zwei Drittel des
  Freitexts**. Mit ihm steigt der Anteil Leads mit ≥1.000 Zeichen Beschreibung von 14,6 % auf
  **32,9 %**. `has_detailed_description` rechnet deshalb über beide Ebenen. Messung +
  Produkt-Konsequenz: `docs/data-sources.md`, Abschnitt „Wie viel Inhalt steht wirklich drin?".
  **Quellen nie zusammen zitieren:** TED 43,5 % reich / Ø 1,68 Lose gegen DÖE 20,8 % / Ø 1,00
  (der `eforms-sdk-0.1`-Dialekt kennt keine Losstruktur). DÖE liefert 9,7 % aller Bau-Leads
  (CPV 45), aber 0 % bei Finanz/Nahrung und 0,1 % bei Pharma — unterschwellig heisst kommunaler
  Bau und Wartung, nicht „ueberall etwas mehr".

### Fallstrick, der schon zugeschlagen hat
`build_lead_cpv` wurde einmal **über** `build_doe_buyer_profile` geschrieben. Der CLI-Aufruf
blieb stehen → jeder `gold`-Lauf brach danach mit `AttributeError` ab, aber erst **nach**
`lead-export`, also nach der teuren Hälfte; alle Tabellen dahinter blieben still veraltet.
`tests/test_plumbing.py::test_cli_gold_builders_exist` prüft das jetzt in Millisekunden.

## Stufe-1-KPIs 1.1–1.4 gebaut (2026-07-23)

Vier Felder aus dem `attributes`-Sammelfeld in `lead_export` (`gold._lead_context_sql`) —
**in EINEM Durchlauf** gelesen, statt ~2,5 h Voll-Reparse. Genau dafuer ist `attributes` da.
Alle Werte auf **ein englisches Vokabular** gemappt (eForms-Codes + Legacy-Labels), in
`tests/test_plumbing.py::_EXPORT_VOCAB` festgenagelt — waechst das Mapping, muss die
Allow-Liste mitwachsen, sonst rutscht ein roher Code wie `cga-mun` ins Frontend.

| Feld | alle Leads | offene Leads | Nutzen |
|---|---:|---:|---|
| `regulatory_regime` | 98,2 % | 95,1 % | VOB/VgV/UVgO/SektVO-Filter — hoechste Abdeckung im Inventar |
| `buyer_type` | 80,0 % | 65,9 % | Vergabestelle-Tab, Grundlage fuer „Kaeufer-Zwillinge" |
| `buyer_activity` | 85,9 % | 67,5 % | dito |
| `documents_url` | 13,6 % | **96,6 %** | ersetzt `source_url` (32,5 % bei offenen) |
| `is_nationwide` | 4.144 Leads | — | steuert den Ortsfilter, s. u. |

**1.2 war eine Reparatur, kein Feature.** `RealizedLocation.Address.Region = anyw*` heisst
„an keinen Ort gebunden". Diese 4.144 Leads fielen aus **jeder** Umkreis- und Regionssuche,
obwohl sie zu jedem Standort passen. Regel liegt jetzt zentral in `geo.nationwide_clause()`
— `geo.search()` **und** `app/radius_suche.py` bauen ihr SQL getrennt und hatten den Fehler
deshalb doppelt. Konvention: bei gesetztem Radius heisst **`dist_km IS NULL` = bundesweit**,
nicht „unbekannt" (fuer eine ortsunabhaengige Leistung ist die Entfernung zur Vergabestelle
keine Aussage). Sortiert an den Rand des Umkreises: hinter alle echten Nahtreffer, aber vor
dem Abschneiden durch `limit`. Muenchen 25 km: 4.987 → 9.071 Leads.

### ✅ Behoben: zwei notice_id-Formate in Silber (2026-07-29)
Der Monats-Archiv-Ingest schrieb `00450024_2026` (zero-padded, Unterstrich), der Live-/DÖE-
Ingest `450024-2026` (Bindestrich). Beim Monatswechsel ersetzt das Archiv den Live-Stand →
alle Gold-Zeilen auf der Alt-Form verwaisen. **Zwei Teile, beide erledigt:**
1. **Prävention (Ingest):** `schema.normalize_notice_id` (Regex `^0*(\d+)[-_](\d{4})$` → `\1_\2`)
   ist an **beiden** Silber-Pfaden verdrahtet (`silver.py:55` Archiv, `:128` Live/DÖE) — künftige
   Ingests schreiben immer kanonisch, kein Drift mehr.
2. **Bestand (Migration):** `scripts/normalize_notice_ids.py` (idempotent, datei-weise atomar,
   0 Kollisionen gemessen) hat den Vor-Fix-Bestand kanonisiert — **217,7 Mio. ID-Werte** über
   9 Silber-Tabellen + 25 Gold-Parquets (inkl. Nachfolge-Kanten `predecessor`/`successor` und
   `award_notice_id`). Verifiziert: 0 nicht-kanonische TED-IDs, 0 neue FK-Waisen, 46 Tests grün.
   **Bewusst NICHT angefasst** — der TED-öffentliche `publication_number`-Raum (Bindestrich ist
   dort kanonisch, steckt in Award-Link-Joins `publication_number=ref_publication_number` + TED-URLs)
   und der **DÖE-Namensraum** (UUIDs / reine Zahlen wie `2f383c64-…` / `19572346` — matchen das
   Muster nicht, würden sonst mit TED kollidieren). Regressions-Guard: `test_plumbing.py::
   test_normalize_notice_id_canonical_and_idempotent` + `::test_silver_gold_notice_ids_are_canonical`.

**Separat offen (KEIN Formatproblem):** 551 `leads` (source=f02, laufender Monat) referenzieren
Live-Notices, die das **Teilmonats-Archiv** von 2026-07 (noch) nicht enthält — ihre kanonische Form
fehlt komplett in Silber (nachgemessen: durch Normalisierung nicht heilbar). Sie verschwinden beim
nächsten Voll-Gold-Rebuild bzw. wenn das Monatsarchiv vollständig ist. Echter Fix: Live-Stand nicht
durch ein **partielles** Monatsarchiv ersetzen lassen (eigenes Ticket).

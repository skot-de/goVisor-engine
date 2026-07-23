# DB-Audit & Härtung

**Stand:** 2026-07-18. Ziel des Nutzers: „100 % Datenqualität". Ehrliche Definition:
*buchstäblich* vollständig+fehlerfrei ist unmöglich — TED selbst hat echte Lücken
(Wert-Abdeckung 2024 nur 35 %), Tippfehler und legitime Leerfälle (aufgehobene
Vergaben). **Erreichbar = 100 % gehärtet:** jeder *erkennbare* Fehler geflaggt +
in der Review-Queue, jede *korrigierbare* Inkonsistenz gefixt, jeder Wert mit
Konfidenz. Silber bleibt verlustfrei; nichts Falsches wird still als Wahr geliefert.

## Audit-Ergebnis (gemessen, `scripts/db_audit.py`)

**Solide:** Verlustfreiheit intakt (attributes deckt alle 1.316.049 Notices, 0 fehlend);
keine Waisen-FKs; keine doppelten notice_id; cpv_main alle valide; Deflator vollständig.

**Entwarnt (sah schlimm aus, ist korrekt):**
- `award_date < publication_date` (363k): erwartet — Zuschlag liegt vor seiner Bekanntmachung.
- 80.526 CANs ohne Gewinner: ~79k echte „kein Zuschlag/aufgehoben" (0 mit Gewinner in awards,
  nur 1.212 mit Contractor im Roh-XML) — keine Parser-Lücke.
- 69k Award-„Duplikate": 11.622 sind Konsortien (mehrere echte Gewinner/Los), nur ~1.233 echt doppelt.

## Gehärtet (umgesetzt 2026-07-18)

- **quality-Flags erweitert** (`build_quality`): `wert_verdaechtig_niedrig` (100–1000),
  `waehrung_fremd`, `schaetzwert_negativ`, `datum_start_nach_ende`, `bieterzahl_unplausibel`
  (num_tenders <0 / >500 / sme>total), zusätzlich zu `laufzeit_unplausibel` u. a.
- **Wert währungsbereinigt:** `final_value_clean` nur noch bei plausibel **UND** EUR — Fremdwährung
  verfälscht Bänder/Median nicht mehr (verifiziert: 0 Nicht-EUR in value_clean).
- **Review-Queue** (`build_review_queue` → `review_queue.parquet`): harte, korrigierbare Fehler
  als Worklist mit Beleg-Link. Aktuell **5.686** (laufzeit 3.394, ende_vor_vergabe 1.107,
  bieterzahl 1.075, wert_absurd_hoch 109, datum 25, schaetzwert 9). Info-/systemische Flags
  bleiben in `quality` sichtbar, verstopfen aber die Queue nicht.
- **Lead-Dedup** (`build_leads`): Mehrfach-Lose desselben Projekts (Käufer+Amtsinhaber+Ende+CPV)
  als Cluster; `ist_hauptlos` + `lose_im_cluster`. Nichts gelöscht; Radar zeigt per Default
  Hauptlose (60.761 von 70.271; 9.510 Neben-Lose ausblendbar). Größter Cluster: 384 Lose (DB-Bahn).
- **Dashboard:** Filter „Nur Hauptlos je Projekt" (Default) + „Unplausible Fälligkeit einbeziehen";
  Spalte „Lose"; Review-Queue-Expander.

## Verbleibende Kern-Schwäche: Entity-Resolution (eigenes Projekt)

Die strukturelle Baustelle. Gemessen: **36 % nur-Name** (Konfidenz 0,4), 18 % unaufgelöst,
Ø-Konfidenz 0,47; Großkäufer wie DB Netz nur namensbasiert; sichtbare Fragmentierung
(„Vergabekammer des Bundes" vs „…beim Bund" = zwei Entitäten). Wurzel des Incumbent-/
Chain-Problems, limitiert jede Käufer-/Firmen-Aggregation.

**Umgesetzt (2026-07-18), gemessen:**
1. **Namens-Kanonik** in `normalize_company`: Klammer-Zusätze (Bukr/Rang-Annotationen),
   „vertreten durch …", Abteilungs-Anhängsel (nach Trennzeichen), führender Artikel, Bukr-Nr.
   An echten Namen getestet: Buyer-Schlüssel −14 % OHNE Über-Merging (Landesämter bleiben
   getrennt). Nebeneffekt: bessere HR-Treffer (25,0 → 26,6 %).
2. **Instabile eForms-IDs entfernt:** UUID-artige `national_id` (pro-Dokument-ORG-Referenz)
   taugt nicht als Schlüssel → fällt auf kanonisierten Namen. `id:`-UUIDs 7.082 → 65.
3. Ergebnis: Entitäten 222.942 → **210.573** (−5,5 %), Ø-Konfidenz 0,474 → 0,476 (flach, weil
   die falsch-sicheren UUIDs ehrlich abgewertet werden). 69/69 Tests grün.

**Ehrliches Fazit — Entity-Resolution ist NICHT der Deckel auf dem Signal:**
- Saubere Subset-Incumbent-Rate **unverändert 18 %** — die Entity-Härtung bewegt sie nicht.
  Der 7-%-Rohwert ist der Ketten-Paarungs-Artefakt (`contract_chains`, s. plan-Doc), nicht
  Entity-Fragmentierung. 18 % ist der *echte* Wert (reale Konkurrenz + nicht verknüpfbare
  Re-Wins unter Tochter/ARGE/Umbenennung).
- Rest-Fragmentierung der Groß-Entitäten ist **großteils legitim:** Compound-Käufer
  („DB Netz AG **und** DB Station&Service **und** …") und Regional-/Subeinheiten. Diese zu
  mergen hieße **falsche JOINs erzeugen** — schlimmer als Fragmentierung. Personen, Ausland,
  ARGE lösen prinzipiell nicht auf. „100 % aufgelöst" ist kein reales Ziel.
- **Subeinheiten-Bündelung** („DB Netz Regionalbereich X" → „DB Netz") gehört in die
  **redaktionelle Gruppen-Ebene** (`dim_company_group`, das „CANCOM"-Werkzeug), nicht in
  schärfere Entity-Regex — konsistent mit Fakt-vs-redaktionell.

**Latente Fragilität → GEFIXT:** `build_entities` schreibt `entities` und `party_entity`
nacheinander; ein Absturz dazwischen (hier einmal durch RAM-Druck passiert) hinterlässt
Waisen, die Leads still verlieren. Jetzt doppelt abgesichert: `verify.gold_integrity` prüft
FK-Waisen (Exit 1 bei Verstoß), und ein Fail-Fast-Guard in der Gold-Pipeline bricht nach
`build_entities` ab, wenn `party_entity → entities` Waisen hat.

## Unternehmensgruppen (redaktionell) — E-Mail-Domain-Clustering

`seed_groups` schlägt Gruppen vor (nie Handkorrekturen überschreiben; `source`:
`manual` > `auto_domain` > `seed`). Neben dem Namensstamm nutzt es jetzt die
**E-Mail-Domain** — aber **gemessen kontaminiert**: die TED-Mail ist oft ein geteilter
Vergabe-Kontakt, keine Eigendomain (@deutschebahn.com gruppierte 2.630 fremde Lieferanten;
@bayern.de warf 355 Ämter zusammen). Zwei Schutzregeln (`domain_group_label`):
1. **Behörden-/Portaldomains blocken** (`_PUBLIC_DOMAIN_SLDS`: bund, bayern, …, deutschebahn).
2. **Namens-Korroboration** — Domain-Kern muss im Firmennamen vorkommen, sonst kein Merge.

Ergebnis: saubere kommerzielle Familien (BECHTLE, STRABAG, REMONDIS, WISAG, SIEMENS,
TELEKOM, SPIE, PreZero, Viatris, Pharma HEXAL/ALIUD/RATIOPHARM).

**Entscheidung (gemessen): Namensstamm gibt KEINE Auto-Gruppe mehr.** Er ist zu rauschig —
mergt unabhängige Firmen (144 „Müller", 1224 „Ingenieurbüro") und öffentliche Stellen.
Auto-Gruppe entsteht NUR bei Domain-Bestätigung (`auto_domain`); zusätzlich ein
`looks_public`-Namensgate + Behörden-/Portal-Domain-Blockliste. Firmen ohne bestätigende
Domain bleiben ungruppiert (Label leer, zur Handkuratierung). `source`: manual > auto_domain > seed.

**Dashboard:** Roll-up über Amtsinhaber-Gruppe UND Käufer-Gruppe (entity→entity_group→
dim_company_group; Join verifiziert duplikatfrei). Für öffentliche Käufer („Land X", die
bewusst KEINE Firmengruppe haben) ein fakt-basierter **Bundesland-Filter aus `buyer_nuts`**
(100 % Abdeckung, NUTS-1 → Bundesland) — das bedient „Käufergruppe Land X" zuverlässig.
